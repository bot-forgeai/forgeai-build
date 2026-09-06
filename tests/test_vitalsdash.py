import json
import os
import urllib.request

import pytest

from vitalsdash.__main__ import build_arg_parser, parse_thresholds
from vitalsdash.data import load_groups, load_vitals
from vitalsdash.server import make_server

SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "..", "vitalsdash", "sample", "demo.csv")
SAMPLE_CSV_2 = os.path.join(os.path.dirname(__file__), "..", "vitalsdash", "sample", "demo2.csv")


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


def test_load_vitals_ignores_non_numeric_columns(tmp_path):
    p = tmp_path / "disklike.csv"
    p.write_text(
        "timestamp,boot_id,uptime_hours\n"
        "2026-01-01T00:00:00,5a38304b-cdb1-4cd6-9fdb-4d8bc1b81f27,5.35\n"
        "2026-01-01T01:00:00,5a38304b-cdb1-4cd6-9fdb-4d8bc1b81f27,5.47\n"
    )
    metrics, records = load_vitals(str(p))
    assert metrics == ["uptime_hours"]
    assert len(records) == 2
    assert records[0]["uptime_hours"] == 5.35
    assert "boot_id" not in records[0]


def test_load_groups_maxes_metric_per_boot(tmp_path):
    p = tmp_path / "disklike.csv"
    p.write_text(
        "timestamp,boot_id,sectors_written\n"
        "2026-01-01T00:00:00,boot-a,100\n"
        "2026-01-01T01:00:00,boot-a,150\n"
        "2026-01-01T02:00:00,boot-b,10\n"
        "2026-01-01T03:00:00,boot-b,40\n"
    )
    column, labels, per_metric = load_groups(str(p))
    assert column == "boot_id"
    assert labels == ["boot-a", "boot-b"]
    assert per_metric == {"sectors_written": [150.0, 40.0]}


def test_load_groups_none_when_no_non_numeric_column():
    column, labels, per_metric = load_groups(SAMPLE_CSV)
    assert column is None
    assert labels == []
    assert per_metric == {}


def test_load_groups_none_when_multiple_non_numeric_columns_and_no_group_by(tmp_path):
    p = tmp_path / "twocols.csv"
    p.write_text(
        "timestamp,boot_id,host,sectors_written\n"
        "2026-01-01T00:00:00,boot-a,pi-1,100\n"
        "2026-01-01T01:00:00,boot-b,pi-1,10\n"
    )
    column, labels, per_metric = load_groups(str(p))
    assert column is None
    assert labels == []
    assert per_metric == {}


def test_load_groups_uses_explicit_group_by_with_multiple_non_numeric_columns(tmp_path):
    p = tmp_path / "twocols.csv"
    p.write_text(
        "timestamp,boot_id,host,sectors_written\n"
        "2026-01-01T00:00:00,boot-a,pi-1,100\n"
        "2026-01-01T01:00:00,boot-b,pi-1,10\n"
    )
    column, labels, per_metric = load_groups(str(p), group_by="boot_id")
    assert column == "boot_id"
    assert labels == ["boot-a", "boot-b"]
    assert per_metric == {"sectors_written": [100.0, 10.0]}


def test_load_groups_group_by_unknown_column_returns_none(tmp_path):
    p = tmp_path / "disklike.csv"
    p.write_text(
        "timestamp,boot_id,sectors_written\n"
        "2026-01-01T00:00:00,boot-a,100\n"
    )
    column, labels, per_metric = load_groups(str(p), group_by="nope")
    assert column is None
    assert labels == []
    assert per_metric == {}


def test_load_vitals_requires_timestamp_column(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("temp_c\n50.0\n")
    with pytest.raises(ValueError):
        load_vitals(str(p))


def test_parse_thresholds_parses_metric_value_pairs():
    assert parse_thresholds(["temp_c=70", "load1=4"]) == {"temp_c": 70.0, "load1": 4.0}


def test_parse_thresholds_empty_when_none():
    assert parse_thresholds(None) == {}


def test_parse_thresholds_rejects_missing_equals():
    with pytest.raises(ValueError):
        parse_thresholds(["temp_c"])


@pytest.fixture
def running_server():
    server = make_server(SAMPLE_CSV, port=0, thresholds={"temp_c": 44.0})
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
    assert payload["thresholds"] == {"temp_c": 44.0}


def test_index_page_serves_html(running_server):
    port = running_server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
        assert resp.status == 200
        body = resp.read().decode()
    assert "<title>vitalsdash</title>" in body


def test_index_page_includes_histogram_rendering(running_server):
    port = running_server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
        body = resp.read().decode()
    assert "histogramSvg" in body
    assert "hist-bar" in body
    assert "charts-row" in body


def test_parses_compare_flag():
    args = build_arg_parser().parse_args([SAMPLE_CSV, "--compare", SAMPLE_CSV_2])
    assert args.compare == SAMPLE_CSV_2


def test_compare_defaults_to_none():
    args = build_arg_parser().parse_args([SAMPLE_CSV])
    assert args.compare is None


def test_parses_bar_by_flag():
    args = build_arg_parser().parse_args([SAMPLE_CSV, "--bar-by", "host"])
    assert args.bar_by == "host"


def test_bar_by_defaults_to_none():
    args = build_arg_parser().parse_args([SAMPLE_CSV])
    assert args.bar_by is None


@pytest.fixture
def comparing_server():
    server = make_server(SAMPLE_CSV, port=0, compare_path=SAMPLE_CSV_2)
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_api_vitals_includes_both_series_when_comparing(comparing_server):
    port = comparing_server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/vitals") as resp:
        payload = json.loads(resp.read())
    assert len(payload["series"]) == 2
    assert payload["series"][0]["label"] == "demo.csv"
    assert payload["series"][1]["label"] == "demo2.csv"
    assert len(payload["series"][1]["records"]) == 7


def test_api_vitals_single_series_when_not_comparing(running_server):
    port = running_server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/vitals") as resp:
        payload = json.loads(resp.read())
    assert len(payload["series"]) == 1
    assert payload["series"][0]["label"] == "demo.csv"


def test_index_page_shows_both_sources_when_comparing(comparing_server):
    port = comparing_server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
        body = resp.read().decode()
    assert "demo.csv" in body
    assert "demo2.csv" in body
    assert "series-block" in body


@pytest.fixture
def grouped_server(tmp_path):
    p = tmp_path / "disklike.csv"
    p.write_text(
        "timestamp,boot_id,sectors_written\n"
        "2026-01-01T00:00:00,boot-a,100\n"
        "2026-01-01T01:00:00,boot-b,10\n"
    )
    server = make_server(str(p), port=0)
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_api_vitals_includes_group_for_boot_id_style_csv(grouped_server):
    port = grouped_server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/vitals") as resp:
        payload = json.loads(resp.read())
    group = payload["series"][0]["group"]
    assert group["column"] == "boot_id"
    assert group["labels"] == ["boot-a", "boot-b"]
    assert group["values"] == {"sectors_written": [100.0, 10.0]}


def test_api_vitals_group_is_none_without_group_column(running_server):
    port = running_server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/vitals") as resp:
        payload = json.loads(resp.read())
    assert payload["series"][0]["group"] is None


def test_index_page_includes_bar_chart_rendering(grouped_server):
    port = grouped_server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
        body = resp.read().decode()
    assert "barChartSvg" in body
    assert "bar-bar" in body


@pytest.fixture
def explicit_group_server(tmp_path):
    p = tmp_path / "twocols.csv"
    p.write_text(
        "timestamp,boot_id,host,sectors_written\n"
        "2026-01-01T00:00:00,boot-a,pi-1,100\n"
        "2026-01-01T01:00:00,boot-b,pi-1,10\n"
    )
    server = make_server(str(p), port=0, group_by="boot_id")
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_api_vitals_uses_explicit_group_by_with_ambiguous_columns(explicit_group_server):
    port = explicit_group_server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/vitals") as resp:
        payload = json.loads(resp.read())
    group = payload["series"][0]["group"]
    assert group["column"] == "boot_id"
    assert group["labels"] == ["boot-a", "boot-b"]
    assert group["values"] == {"sectors_written": [100.0, 10.0]}


def test_unknown_path_404s(running_server):
    port = running_server.server_address[1]
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/nope")
        assert False, "expected HTTPError"
    except urllib.error.HTTPError as e:
        assert e.code == 404
