import subprocess
import sys
import threading
import time

from kvlog.server import KVServer


def run_cli(db_path, *args):
    return subprocess.run(
        [sys.executable, "-m", "kvlog", "--db", db_path, *args],
        capture_output=True,
        text=True,
    )


def run_remote_cli(host, port, *args):
    return subprocess.run(
        [sys.executable, "-m", "kvlog", "--remote", f"{host}:{port}", *args],
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


def test_fsync_never_flag_still_works(tmp_path):
    db = str(tmp_path / "cli.db")
    result = subprocess.run(
        [sys.executable, "-m", "kvlog", "--db", db, "--fsync", "never", "put", "name", "ada"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    result = run_cli(db, "get", "name")
    assert result.stdout.strip() == "ada"


def test_invalid_fsync_flag_rejected(tmp_path):
    db = str(tmp_path / "cli.db")
    result = subprocess.run(
        [sys.executable, "-m", "kvlog", "--db", db, "--fsync", "sometimes", "put", "a", "1"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_remote_put_and_get(tmp_path):
    db = str(tmp_path / "net.db")
    server = KVServer(("127.0.0.1", 0), db)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        result = run_remote_cli(host, port, "put", "name", "ada")
        assert result.returncode == 0
        result = run_remote_cli(host, port, "get", "name")
        assert result.returncode == 0
        assert result.stdout.strip() == "ada"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_remote_get_missing_key_errors_cleanly(tmp_path):
    db = str(tmp_path / "net.db")
    server = KVServer(("127.0.0.1", 0), db)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        result = run_remote_cli(host, port, "get", "nope")
        assert result.returncode == 1
        assert "no such key" in result.stderr
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_replicate_picks_up_leader_writes(tmp_path):
    leader_db = str(tmp_path / "leader.db")
    replica_db = str(tmp_path / "replica.db")
    server = KVServer(("127.0.0.1", 0), leader_db)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    proc = None
    try:
        server.store.put("a", "1")
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "kvlog", "--db", replica_db,
                "replicate", "--leader", f"{host}:{port}", "--poll-interval", "0.1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.time() + 10
        result = None
        while time.time() < deadline:
            result = run_cli(replica_db, "get", "a")
            if result.returncode == 0:
                break
            time.sleep(0.1)
        assert result is not None and result.returncode == 0
        assert result.stdout.strip() == "1"

        # A write after the replica started should also show up.
        server.store.put("b", "2")
        deadline = time.time() + 10
        while time.time() < deadline:
            result = run_cli(replica_db, "get", "b")
            if result.returncode == 0:
                break
            time.sleep(0.1)
        assert result.returncode == 0
        assert result.stdout.strip() == "2"
    finally:
        if proc is not None:
            proc.terminate()
            proc.wait(timeout=5)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_version():
    result = subprocess.run(
        [sys.executable, "-m", "kvlog", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout or "0.1" in result.stdout
