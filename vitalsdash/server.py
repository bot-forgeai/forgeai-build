"""Minimal HTTP server for vitalsdash: one JSON endpoint, one HTML page.

Uses only the standard library (http.server) so it can run on
hardware with no network access to fetch dependencies, and serves a
single self-contained HTML page that draws its own SVG line charts —
no CDN scripts, no build step.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .data import load_vitals

PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>vitalsdash</title>
<style>
  body {{ font-family: monospace; background: #111; color: #eee; margin: 2rem; }}
  h1 {{ font-size: 1.1rem; color: #8fd; }}
  .chart {{ margin-bottom: 2rem; }}
  .chart h2 {{ font-size: 0.9rem; color: #aaa; margin: 0 0 0.3rem 0; }}
  svg {{ background: #1a1a1a; border: 1px solid #333; }}
  polyline {{ fill: none; stroke: #8fd; stroke-width: 1.5; }}
  text {{ fill: #888; font-size: 9px; }}
</style>
</head>
<body>
<h1>vitalsdash — {source}</h1>
<div id="charts"></div>
<script>
async function main() {{
  const res = await fetch('/api/vitals');
  const data = await res.json();
  const container = document.getElementById('charts');
  const W = 700, H = 140, PAD = 20;

  for (const metric of data.metrics) {{
    const values = data.records.map(r => r[metric]);
    const min = Math.min(...values), max = Math.max(...values);
    const range = (max - min) || 1;

    const points = values.map((v, i) => {{
      const x = PAD + (i / Math.max(values.length - 1, 1)) * (W - 2 * PAD);
      const y = H - PAD - ((v - min) / range) * (H - 2 * PAD);
      return `${{x.toFixed(1)}},${{y.toFixed(1)}}`;
    }}).join(' ');

    const div = document.createElement('div');
    div.className = 'chart';
    div.innerHTML = `
      <h2>${{metric}} (min ${{min.toFixed(2)}}, max ${{max.toFixed(2)}}, latest ${{values[values.length - 1]}})</h2>
      <svg width="${{W}}" height="${{H}}">
        <polyline points="${{points}}" />
        <text x="${{PAD}}" y="${{H - 4}}">${{data.records[0] ? data.records[0].timestamp : ''}}</text>
        <text x="${{W - 140}}" y="${{H - 4}}">${{data.records.length ? data.records[data.records.length - 1].timestamp : ''}}</text>
      </svg>`;
    container.appendChild(div);
  }}
}}
main();
</script>
</body>
</html>
"""


def _make_handler(csv_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # keep stdout quiet on a resource-constrained host

        def do_GET(self):
            if self.path == "/api/vitals":
                metric_names, records = load_vitals(csv_path)
                body = json.dumps({"metrics": metric_names, "records": records}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/":
                body = PAGE_TEMPLATE.format(source=csv_path).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

    return Handler


def make_server(csv_path, host="127.0.0.1", port=8099):
    """Build (but do not start) a ThreadingHTTPServer serving csv_path."""
    return ThreadingHTTPServer((host, port), _make_handler(csv_path))
