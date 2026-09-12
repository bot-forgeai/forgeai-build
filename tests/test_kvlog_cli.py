import subprocess
import sys


def run_cli(db_path, *args):
    return subprocess.run(
        [sys.executable, "-m", "kvlog", "--db", db_path, *args],
        capture_output=True,
        text=True,
    )


def test_put_and_get(tmp_path):
    db = str(tmp_path / "cli.db")
    result = run_cli(db, "put", "name", "ada")
    assert result.returncode == 0
    result = run_cli(db, "get", "name")
    assert result.returncode == 0
    assert result.stdout.strip() == "ada"


def test_get_missing_key_errors_cleanly(tmp_path):
    db = str(tmp_path / "cli.db")
    result = run_cli(db, "get", "nope")
    assert result.returncode == 1
    assert "no such key" in result.stderr


def test_delete(tmp_path):
    db = str(tmp_path / "cli.db")
    run_cli(db, "put", "x", "1")
    result = run_cli(db, "delete", "x")
    assert result.returncode == 0
    result = run_cli(db, "get", "x")
    assert result.returncode == 1


def test_keys_and_dump(tmp_path):
    db = str(tmp_path / "cli.db")
    run_cli(db, "put", "a", "1")
    run_cli(db, "put", "b", "2")
    result = run_cli(db, "keys")
    assert result.stdout.split() == ["a", "b"]
    result = run_cli(db, "dump")
    lines = result.stdout.strip().splitlines()
    assert lines == ['a\t"1"', 'b\t"2"']


def test_prefix(tmp_path):
    db = str(tmp_path / "cli.db")
    run_cli(db, "put", "user:1", "ada")
    run_cli(db, "put", "user:2", "bob")
    run_cli(db, "put", "group:1", "admins")
    result = run_cli(db, "prefix", "user:")
    assert result.returncode == 0
    assert result.stdout.strip().splitlines() == ['user:1\t"ada"', 'user:2\t"bob"']


def test_range(tmp_path):
    db = str(tmp_path / "cli.db")
    for k in ["a", "b", "c", "d"]:
        run_cli(db, "put", k, k.upper())
    result = run_cli(db, "range", "--start", "b", "--end", "c")
    assert result.returncode == 0
    assert result.stdout.strip().splitlines() == ['b\t"B"', 'c\t"C"']


def test_compact_reports_sizes(tmp_path):
    db = str(tmp_path / "cli.db")
    for i in range(10):
        run_cli(db, "put", "k", str(i))
    result = run_cli(db, "compact")
    assert result.returncode == 0
    assert "compacted:" in result.stdout
    assert "1 keys" in result.stdout
