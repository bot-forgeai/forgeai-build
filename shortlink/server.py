"""Stdlib HTTP server for shortlink.

Routes:
  GET  /                    HTML page: shorten form + link list
  POST /api/shorten         body {"url": "...", "code": "..." (optional),
                                   "ttl_seconds": 3600 (optional)}
                             -> {"code": "...", "short_url": "/<code>"}
  GET  /api/links           -> [{"code", "url", "created_at", "expires_at",
                                  "expired", "clicks"}, ...]
  GET  /api/stats/<code>    -> {"code", "url", "created_at", "clicks",
                                  "last_clicked_at", "expires_at", "expired"}
  GET  /qr/<code>           SVG QR code encoding this server's own short URL
                             (built from the request's Host header, so it
                             resolves correctly whether served on localhost
                             or a LAN address); 404 for an unknown code
  GET  /<code>              302 redirect to the stored URL, records a click;
                             410 if the link has expired
"""
import html
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import qrcode
import qrcode.image.svg

from . import db


def _qr_svg(data):
    """Render `data` (a URL) as an SVG QR code, no raster deps required."""
    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()


def _page(links):
    rows = "".join(
        f"<tr><td><a href='/{html.escape(l['code'])}'>/{html.escape(l['code'])}</a>"
        f"{' (expired)' if l['expired'] else ''}</td>"
        f"<td>{html.escape(l['url'])}</td><td>{l['clicks']}</td>"
        f"<td><a href='/qr/{html.escape(l['code'])}'>"
        f"<img src='/qr/{html.escape(l['code'])}' width='60' height='60' alt='QR code'></a></td></tr>"
        for l in links
    )
    return f"""<!DOCTYPE html>
<html><head><title>shortlink</title></head>
<body>
<h1>shortlink</h1>
<form id="shorten-form">
  <input name="url" type="url" placeholder="https://example.com/..." required style="width:20em">
  <button type="submit">Shorten</button>
</form>
<p id="result"></p>
<table border="1" cellpadding="4">
<tr><th>short</th><th>url</th><th>clicks</th><th>qr</th></tr>
{rows}
</table>
<script>
document.getElementById('shorten-form').addEventListener('submit', async (e) => {{
  e.preventDefault();
  const url = e.target.url.value;
  const resp = await fetch('/api/shorten', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{url}}),
  }});
  const data = await resp.json();
  if (resp.ok) {{
    document.getElementById('result').innerHTML =
      'Created: <a href="/' + data.code + '">/' + data.code + '</a>';
    setTimeout(() => location.reload(), 800);
  }} else {{
    document.getElementById('result').textContent = 'Error: ' + data.error;
  }}
}});
</script>
</body></html>"""


def make_server(db_path, host="127.0.0.1", port=8100):
    conn = db.connect(db_path)
    # ThreadingHTTPServer runs each request on its own thread, and sqlite3
    # connections only tolerate one caller at a time even with
    # check_same_thread=False -- this lock serializes every db access.
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send_json(self, payload, status=200):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                with lock:
                    links = db.list_links(conn)
                body = _page(links).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/api/links":
                with lock:
                    self._send_json(db.list_links(conn))
                return
            if path.startswith("/api/stats/"):
                code = path[len("/api/stats/"):]
                with lock:
                    stats = db.get_stats(conn, code)
                if stats is None:
                    self._send_json({"error": "not found"}, status=404)
                else:
                    self._send_json(stats)
                return
            if path.startswith("/qr/"):
                code = path[len("/qr/"):]
                with lock:
                    status = db.get_link_status(conn, code)
                if status is None:
                    self._send_json({"error": "not found"}, status=404)
                    return
                target = f"http://{self.headers.get('Host', 'localhost')}/{code}"
                body = _qr_svg(target)
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            code = path.lstrip("/")
            with lock:
                status = db.get_link_status(conn, code) if code else None
                if status is not None and not status["expired"]:
                    db.record_click(conn, code)
            if status is None:
                self._send_json({"error": "not found"}, status=404)
                return
            if status["expired"]:
                self._send_json({"error": "link expired"}, status=410)
                return
            self.send_response(302)
            self.send_header("Location", status["url"])
            self.end_headers()

        def do_POST(self):
            if urlparse(self.path).path != "/api/shorten":
                self._send_json({"error": "not found"}, status=404)
                return
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._send_json({"error": "invalid JSON body"}, status=400)
                return
            url = payload.get("url")
            if not url:
                self._send_json({"error": "'url' is required"}, status=400)
                return
            ttl_seconds = payload.get("ttl_seconds")
            try:
                with lock:
                    code = db.create_link(
                        conn, url, code=payload.get("code"), ttl_seconds=ttl_seconds
                    )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=409)
                return
            self._send_json({"code": code, "short_url": f"/{code}"}, status=201)

    server = ThreadingHTTPServer((host, port), Handler)
    server.shortlink_conn = conn
    return server
