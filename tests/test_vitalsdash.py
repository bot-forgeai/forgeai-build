import json
import os
import urllib.request

import pytest

from vitalsdash.data import load_vitals
from vitalsdash.server import make_server

SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "..", "vitalsdash", "sample", "demo.csv")


def test_load_vitals_parses_metrics_and_rows():
    metrics, records = load_vitals(SAMPLE_CSV)
    assert metrics == ["temp_c", "load1", "mem_available_mb"]
    assert len(records) == 7
    assert records[0]["timestamp"] == "2026-09-01T00:00:00"
    assert records[0]["temp_c"] == 45.2


def test_load_vitals_skips_malformed_rows(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("timestamp,temp_c\n2026-01-01T00:00:00,50.0\nnot-a-row\n")
    metrics, records = load_vitals(str(p))
    assert metrics == ["temp_c"]
    assert len(records) == 1


def test_load_vitals_requires_timestamp_column(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("temp_c\n50.0\n")
    with pytest.raises(ValueError):
        load_vitals(str(p))


@pytest.fixture
def running_server():
    server = make_server(SAMPLE_CSV, port=0)
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_api_vitals_returns_records(running_server):
    port = running_server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/vitals") as resp:
        assert resp.status == 200
        payload = json.loads(resp.read())
    assert payload["metrics"] == ["temp_c", "load1", "mem_available_mb"]
    assert len(payload["records"]) == 7


def test_index_page_serves_html(running_server):
    port = running_server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
        assert resp.status == 200
        body = resp.read().decode()
    assert "<title>vitalsdash</title>" in body


def test_unknown_path_404s(running_server):
    port = running_server.server_address[1]
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/nope")
        assert False, "expected HTTPError"
    except urllib.error.HTTPError as e:
        assert e.code == 404
