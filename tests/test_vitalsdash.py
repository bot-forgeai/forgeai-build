import json
import os
import urllib.request

import pytest

from vitalsdash.__main__ import build_arg_parser, parse_thresholds, unknown_metrics
from vitalsdash.data import filter_last_days, find_gaps, load_groups, load_vitals
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


def test_version():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "vitalsdash", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout or "0.1" in result.stdout


def test_dashboard_page_plots_x_by_timestamp(running_server):
    port = running_server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
        html = resp.read().decode()
    assert "Date.parse(r.timestamp)" in html
    assert "(times[i] - t0) / tSpan" in html


def test_find_gaps_flags_stalled_logging():
    recs = [{"timestamp": t} for t in (
        "2026-10-09T00:00:00", "2026-10-09T03:00:00", "2026-10-09T06:00:00",
        "2026-10-09T09:00:00", "2026-10-09T20:00:00", "2026-10-09T23:00:00")]
    assert find_gaps(recs) == [
        {"start": "2026-10-09T09:00:00", "end": "2026-10-09T20:00:00", "hours": 11.0}
    ]


def test_find_gaps_empty_for_even_or_unparseable_data():
    even = [{"timestamp": f"2026-10-09T0{h}:00:00"} for h in range(5)]
    assert find_gaps(even) == []
    assert find_gaps([{"timestamp": "x"}] * 5) == []
    assert find_gaps(even[:2]) == []


def test_api_vitals_series_includes_gaps(running_server):
    port = running_server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/vitals") as resp:
        payload = json.loads(resp.read())
    assert payload["series"][0]["gaps"] == []


def test_filter_last_days_windows_from_newest_record():
    recs = [{"timestamp": f"2026-10-{d:02d}T00:00:00"} for d in (1, 5, 9, 10)]
    kept = filter_last_days(recs, 2)
    assert [r["timestamp"][8:10] for r in kept] == ["09", "10"]
    assert filter_last_days(recs, None) is recs


def test_api_vitals_last_days_filters_records(tmp_path):
    p = tmp_path / "v.csv"
    p.write_text("timestamp,temp_c\n2026-10-01T00:00:00,50\n2026-10-10T00:00:00,51\n2026-10-11T00:00:00,52\n")
    server = make_server(str(p), port=0, last_days=2)
    import threading
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/vitals") as resp:
            data = json.load(resp)
        assert len(data["records"]) == 2
    finally:
        server.shutdown()
        server.server_close()


def test_parse_thresholds_accepts_below_syntax():
    from vitalsdash.__main__ import parse_below_metrics

    specs = ["mem_available_mb<100", "temp_c=70"]
    assert parse_thresholds(specs) == {"mem_available_mb": 100.0, "temp_c": 70.0}
    assert parse_below_metrics(specs) == ["mem_available_mb"]


def test_to_rate_per_hour_and_drops_counter_reset():
    from vitalsdash.data import to_rate
    recs = [
        {"timestamp": "2026-01-01T00:00:00", "w": 100.0, "t": 50.0},
        {"timestamp": "2026-01-01T01:00:00", "w": 300.0, "t": 51.0},
        {"timestamp": "2026-01-01T01:30:00", "w": 10.0, "t": 52.0},  # reboot
        {"timestamp": "2026-01-01T02:30:00", "w": 70.0, "t": 53.0},
    ]
    out = to_rate(recs, ["w"])
    assert out == [
        {"timestamp": "2026-01-01T01:00:00", "w/h": 200.0, "t": 51.0},
        {"timestamp": "2026-01-01T02:30:00", "w/h": 60.0, "t": 53.0},
    ]
    assert to_rate(recs, []) is recs


def test_api_vitals_rate_renames_metric(tmp_path):
    import json, threading, urllib.request
    from vitalsdash.server import make_server
    p = tmp_path / "c.csv"
    p.write_text("timestamp,w\n2026-01-01T00:00:00,0\n2026-01-01T02:00:00,50\n")
    srv = make_server(str(p), port=0, rate=["w"])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        d = json.load(urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/api/vitals"))
    finally:
        srv.shutdown(); srv.server_close()
    assert d["metrics"] == ["w/h"]
    assert d["records"][0]["w/h"] == 25.0


def test_page_rounds_latest_value_in_series_label():
    from vitalsdash.server import PAGE_TEMPLATE
    assert "latest ${{fmt(latest)}}" in PAGE_TEMPLATE
    assert "toPrecision(6)" in PAGE_TEMPLATE


def test_unknown_metrics_lists_names_missing_from_columns():
    assert unknown_metrics(["tmp_c", "load1", "nosuch"], ["temp_c", "load1"]) == ["tmp_c", "nosuch"]
    assert unknown_metrics([], ["temp_c"]) == []


@pytest.mark.parametrize("bad", ["0", "-3", "nan", "abc"])
def test_last_days_rejects_non_positive(bad, capsys):
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--last-days", bad, "x.csv"])
    assert "--last-days" in capsys.readouterr().err
    assert build_arg_parser().parse_args(["--last-days", "0.5", "x.csv"]).last_days == 0.5


@pytest.mark.parametrize("bad", ["temp_c=abc", "temp_c", "=70"])
def test_threshold_rejects_malformed_spec(bad, capsys):
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--threshold", bad, "x.csv"])
    assert "--threshold" in capsys.readouterr().err
    assert build_arg_parser().parse_args(["--threshold", "mem<100", "x.csv"]).threshold == ["mem<100"]


def test_missing_csv_exits_cleanly(tmp_path):
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "vitalsdash", str(tmp_path / "nope.csv")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "cannot read" in result.stderr
    assert "Traceback" not in result.stderr


def test_missing_compare_csv_exits_cleanly(tmp_path):
    import subprocess
    import sys

    good = tmp_path / "v.csv"
    good.write_text("timestamp,temp_c\n2026-01-01T00:00:00,50\n")
    result = subprocess.run(
        [sys.executable, "-m", "vitalsdash", "--compare", str(tmp_path / "nope.csv"), str(good)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "--compare" in result.stderr
    assert "Traceback" not in result.stderr


def test_unknown_bar_by_warns(tmp_path):
    import subprocess
    import sys

    good = tmp_path / "v.csv"
    good.write_text("timestamp,temp_c\n2026-01-01T00:00:00,50\n")
    proc = subprocess.Popen(
        [sys.executable, "-m", "vitalsdash", "--port", "0", "--bar-by", "nosuch", str(good)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        line = proc.stderr.readline()
    finally:
        proc.kill()
        proc.communicate()
    assert "--bar-by 'nosuch'" in line


def test_summarize_stats_and_breach_directions():
    from vitalsdash.data import summarize
    recs = [{"timestamp": "t1", "a": 1.0, "b": 10.0}, {"timestamp": "t2", "a": 3.0, "b": 5.0}]
    rows = {r["metric"]: r for r in summarize(["a", "b"], recs, {"a": 2.0, "b": 8.0}, below=["b"])}
    assert (rows["a"]["min"], rows["a"]["mean"], rows["a"]["max"], rows["a"]["latest"]) == (1.0, 2.0, 3.0, 3.0)
    assert rows["a"]["breached"] is True   # 3 > 2
    assert rows["b"]["breached"] is True   # 5 < 8, below-threshold
    assert summarize(["a"], recs, {"a": 5.0})[0]["breached"] is False


def test_summary_flag_prints_table_and_exits_by_breach(capsys, monkeypatch):
    from vitalsdash.__main__ import main
    monkeypatch.setattr("sys.argv", ["vitalsdash", SAMPLE_CSV, "--summary"])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 0
    assert "temp_c" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["vitalsdash", SAMPLE_CSV, "--summary", "--threshold", "temp_c=0"])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1


def test_summary_compare_adds_mean_and_diff_columns(capsys, monkeypatch):
    from vitalsdash.__main__ import main
    monkeypatch.setattr("sys.argv", ["vitalsdash", SAMPLE_CSV, "--summary", "--compare", SAMPLE_CSV])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "mean2" in out and "diff" in out and "+0" in out


def test_format_summary_compare_missing_metric_shows_dash():
    from vitalsdash.__main__ import add_compare_means, format_summary
    rows = [{"metric": "a", "n": 1, "min": 1, "mean": 1.0, "max": 1, "p95": 1, "trend_per_day": None, "latest": 1, "breached": False}]
    assert format_summary(add_compare_means(rows, [])).splitlines()[1].split()[-2:] == ["-", "-"]


def test_summary_json_prints_rows_and_keeps_exit_code(capsys, monkeypatch):
    import json
    import pytest
    from vitalsdash.__main__ import main

    monkeypatch.setattr("sys.argv", ["vitalsdash", SAMPLE_CSV, "--summary", "--json", "--threshold", "temp_c=0"])
    with pytest.raises(SystemExit) as e:
        main()
    rows = json.loads(capsys.readouterr().out)
    assert e.value.code == 1
    assert any(r["metric"] == "temp_c" and r["breached"] for r in rows)


def test_json_without_summary_is_a_usage_error(monkeypatch):
    import pytest
    from vitalsdash.__main__ import main

    monkeypatch.setattr("sys.argv", ["vitalsdash", SAMPLE_CSV, "--json"])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 2


def test_load_vitals_skips_nan_and_inf(tmp_path):
    path = tmp_path / "v.csv"
    path.write_text(
        "timestamp,a,b\n"
        "2026-01-01T00:00:00,1,2\n"
        "2026-01-01T01:00:00,nan,3\n"
        "2026-01-01T02:00:00,inf,4\n"
        "2026-01-01T03:00:00,5,6\n"
    )
    metrics, records = load_vitals(str(path))
    assert [r["a"] for r in records] == [1.0, 5.0]


def test_percentile_interpolates():
    from vitalsdash.data import percentile

    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([0, 10], 95) == 9.5
    assert percentile([7], 95) == 7


def test_summarize_p95_and_trend_per_day():
    from vitalsdash.data import summarize

    recs = [{"timestamp": f"2026-01-0{d}T00:00:00", "a": 10.0 + 2 * (d - 1)} for d in (1, 2, 3)]
    row = summarize(["a"], recs)[0]
    assert abs(row["trend_per_day"] - 2.0) < 1e-9
    assert abs(row["p95"] - 13.8) < 1e-9


def test_summarize_trend_none_without_usable_timestamps():
    from vitalsdash.data import summarize

    one = summarize(["a"], [{"timestamp": "2026-01-01T00:00:00", "a": 1.0}])[0]
    bad = summarize(["a"], [{"timestamp": "x", "a": 1.0}, {"timestamp": "y", "a": 2.0}])[0]
    assert one["trend_per_day"] is None and bad["trend_per_day"] is None


def test_format_summary_shows_p95_and_trend_columns():
    from vitalsdash.__main__ import format_summary
    from vitalsdash.data import summarize

    recs = [{"timestamp": f"2026-01-0{d}T00:00:00", "a": float(d)} for d in (1, 2)]
    out = format_summary(summarize(["a"], recs)).splitlines()
    assert out[0].split()[-3:] == ["p95", "trend/d", "latest"]
    assert out[1].split()[-2] == "+1"


def test_summarize_breach_history_counts_runs_and_last():
    from vitalsdash.data import summarize
    recs = [{"timestamp": f"2026-01-01T0{i}:00:00", "t": v} for i, v in enumerate([60, 80, 90, 50, 85])]
    row = summarize(["t"], recs, {"t": 70.0})[0]
    assert (row["breach_n"], row["breach_longest_run"], row["last_breach"]) == (3, 2, "2026-01-01T04:00:00")
    assert row["breached"] is True


def test_summarize_breach_history_below_and_unthresholded():
    from vitalsdash.data import summarize
    recs = [{"timestamp": f"2026-01-01T0{i}:00:00", "m": v, "x": 1} for i, v in enumerate([50, 120, 90])]
    rows = {r["metric"]: r for r in summarize(["m", "x"], recs, {"m": 100.0}, below=["m"])}
    assert rows["m"]["breach_n"] == 2 and rows["m"]["breach_longest_run"] == 1
    assert rows["x"]["breach_n"] is None


def test_format_summary_shows_breach_columns_only_with_thresholds():
    from vitalsdash.__main__ import format_summary
    from vitalsdash.data import summarize
    recs = [{"timestamp": f"2026-01-01T0{i}:00:00", "t": v} for i, v in enumerate([60, 80, 90])]
    assert "breaches" not in format_summary(summarize(["t"], recs))
    text = format_summary(summarize(["t"], recs, {"t": 70.0}))
    assert "breaches" in text and "2/3" in text and "2026-01-01T02:00:00" in text


def test_freshness_reports_age_and_gaps():
    from datetime import datetime
    from vitalsdash.data import freshness
    recs = [{"timestamp": t} for t in (
        "2026-01-01T00:00:00", "2026-01-01T01:00:00", "2026-01-01T02:00:00", "2026-01-02T02:00:00")]
    f = freshness(recs, now=datetime(2026, 1, 2, 5, 0, 0))
    assert f["newest"] == "2026-01-02T02:00:00"
    assert f["age_hours"] == 3.0
    assert f["gaps"] == 1 and f["longest_gap_hours"] == 24.0
    assert freshness([{"timestamp": "bad"}]) is None


def test_stale_after_exits_1_and_warns(capsys, monkeypatch):
    from vitalsdash.__main__ import main
    monkeypatch.setattr("sys.argv", ["vitalsdash", SAMPLE_CSV, "--summary", "--stale-after", "1"])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 1
    cap = capsys.readouterr()
    assert "stale" in cap.err and "newest sample" in cap.out


def test_stale_after_requires_summary(monkeypatch):
    from vitalsdash.__main__ import main
    monkeypatch.setattr("sys.argv", ["vitalsdash", SAMPLE_CSV, "--stale-after", "1"])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 2
