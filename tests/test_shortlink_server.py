import json
import threading
import urllib.error
import urllib.request

from shortlink.server import make_server


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Surface a 302 as an HTTPError instead of silently following it."""

    def redirect_request(self, *args, **kwargs):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _start(tmp_path):
    server = make_server(str(tmp_path / "test.db"), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


def _post_json(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_shorten_and_redirect(tmp_path):
    server, port = _start(tmp_path)
    try:
        status, body = _post_json(
            f"http://127.0.0.1:{port}/api/shorten", {"url": "https://example.com/page"}
        )
        assert status == 201
        code = body["code"]
        assert body["short_url"] == f"/{code}"

        req = urllib.request.Request(f"http://127.0.0.1:{port}/{code}")
        try:
            _opener.open(req)
            assert False, "expected a redirect, not a followed 200"
        except urllib.error.HTTPError as exc:
            assert exc.code == 302
            assert exc.headers["Location"] == "https://example.com/page"
    finally:
        server.shutdown()


def test_shorten_requires_url(tmp_path):
    server, port = _start(tmp_path)
    try:
        status, body = _post_json(f"http://127.0.0.1:{port}/api/shorten", {})
        assert status == 400
        assert "error" in body
    finally:
        server.shutdown()


def test_shorten_with_explicit_code_conflict(tmp_path):
    server, port = _start(tmp_path)
    try:
        _post_json(f"http://127.0.0.1:{port}/api/shorten", {"url": "https://a.com", "code": "x"})
        status, body = _post_json(
            f"http://127.0.0.1:{port}/api/shorten", {"url": "https://b.com", "code": "x"}
        )
        assert status == 409
    finally:
        server.shutdown()


def test_redirect_records_a_click_visible_in_stats(tmp_path):
    server, port = _start(tmp_path)
    try:
        _, body = _post_json(f"http://127.0.0.1:{port}/api/shorten", {"url": "https://example.com"})
        code = body["code"]

        for _ in range(3):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/{code}")
            except urllib.error.HTTPError:
                pass

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/stats/{code}") as resp:
            stats = json.loads(resp.read())
        assert stats["clicks"] == 3
        assert stats["url"] == "https://example.com"
    finally:
        server.shutdown()


def test_expired_link_returns_410_and_no_click_recorded(tmp_path):
    server, port = _start(tmp_path)
    try:
        _, body = _post_json(
            f"http://127.0.0.1:{port}/api/shorten",
            {"url": "https://example.com", "ttl_seconds": -1},
        )
        code = body["code"]

        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/{code}")
            assert False, "expected 410"
        except urllib.error.HTTPError as exc:
            assert exc.code == 410

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/stats/{code}") as resp:
            stats = json.loads(resp.read())
        assert stats["expired"] is True
        assert stats["clicks"] == 0
    finally:
        server.shutdown()


def test_live_link_reports_not_expired_in_stats(tmp_path):
    server, port = _start(tmp_path)
    try:
        _, body = _post_json(
            f"http://127.0.0.1:{port}/api/shorten",
            {"url": "https://example.com", "ttl_seconds": 3600},
        )
        code = body["code"]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/stats/{code}") as resp:
            stats = json.loads(resp.read())
        assert stats["expired"] is False
        assert stats["expires_at"] is not None
    finally:
        server.shutdown()


def test_unknown_code_returns_404(tmp_path):
    server, port = _start(tmp_path)
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope")
            assert False, "expected 404"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404

        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/stats/nope")
            assert False, "expected 404"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.shutdown()


def test_links_list_and_homepage_render(tmp_path):
    server, port = _start(tmp_path)
    try:
        _post_json(f"http://127.0.0.1:{port}/api/shorten", {"url": "https://example.com/x"})

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/links") as resp:
            links = json.loads(resp.read())
        assert len(links) == 1
        assert links[0]["url"] == "https://example.com/x"

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
            html_body = resp.read().decode()
        assert "example.com/x" in html_body
        assert "shorten-form" in html_body
    finally:
        server.shutdown()
