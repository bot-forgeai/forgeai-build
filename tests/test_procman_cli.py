import json
import sys

import pytest

from procman.__main__ import build_parser


def run_cli(args):
    parser = build_parser()
    ns = parser.parse_args(args)
    return ns.func(ns)


def write_config(tmp_path, data):
    path = tmp_path / "procman.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_validate_good_config(tmp_path, capsys):
    path = write_config(tmp_path, {"services": [{"name": "a", "command": ["echo", "hi"]}]})
    code = run_cli(["validate", path])
    out = capsys.readouterr().out
    assert code == 0
    assert "ok: 1 service" in out
    assert "a: echo hi" in out


def test_validate_bad_config(tmp_path, capsys):
    path = write_config(tmp_path, {"services": []})
    code = run_cli(["validate", path])
    err = capsys.readouterr().err
    assert code == 1
    assert "error:" in err


def test_run_with_max_iterations(tmp_path, capsys):
    status_path = str(tmp_path / "status.json")
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": [sys.executable, "-c", "import time; time.sleep(5)"]}]
    })
    code = run_cli(["run", path, "--log-dir", str(tmp_path / "logs"), "--status", status_path,
                     "--interval", "0.1", "--max-iterations", "2"])
    assert code == 0
    with open(status_path) as f:
        data = json.load(f)
    assert "a" in data


def test_status_command(tmp_path, capsys):
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps({
        "a": {"name": "a", "running": True, "pid": 123, "restarts": 0, "last_exit_code": None, "autorestart": True}
    }))
    code = run_cli(["status", str(status_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "running" in out
    assert "123" in out


def test_status_missing_file(tmp_path, capsys):
    code = run_cli(["status", str(tmp_path / "nope.json")])
    err = capsys.readouterr().err
    assert code == 1
    assert "not found" in err


def test_validate_reports_max_log_bytes(tmp_path, capsys):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["echo", "hi"], "max_log_bytes": 5000}]
    })
    code = run_cli(["validate", path])
    out = capsys.readouterr().out
    assert code == 0
    assert "max_log_bytes: 5000" in out


def test_run_with_max_log_bytes_rotates(tmp_path, capsys):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "a.log").write_bytes(b"x" * 2000)
    status_path = str(tmp_path / "status.json")
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": [sys.executable, "-c", "import sys; sys.exit(0)"]}]
    })
    code = run_cli(["run", path, "--log-dir", str(log_dir), "--status", status_path,
                     "--interval", "0.1", "--max-iterations", "1", "--max-log-bytes", "1000"])
    assert code == 0
    assert (log_dir / "a.log.1").read_bytes() == b"x" * 2000


def test_version():
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "procman", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout or "0.1" in result.stdout
