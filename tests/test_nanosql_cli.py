import pytest

from nanosql.__main__ import main


def run(capsys, argv):
    try:
        main(argv)
        code = 0
    except SystemExit as exc:
        code = exc.code
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_exec_create_and_select(tmp_path, capsys):
    db_path = str(tmp_path / "db.json")
    code, _, _ = run(capsys, ["exec", db_path, "CREATE TABLE t (id INT, name TEXT)"])
    assert code == 0
    code, _, _ = run(capsys, ["exec", db_path, "INSERT INTO t VALUES (1, 'Ada')"])
    assert code == 0
    code, out, _ = run(capsys, ["exec", db_path, "SELECT * FROM t"])
    assert code == 0
    assert "id\tname" in out
    assert "1\tAda" in out
    assert "(1 row(s))" in out


def test_exec_persists_across_invocations(tmp_path, capsys):
    db_path = str(tmp_path / "db.json")
    run(capsys, ["exec", db_path, "CREATE TABLE t (id INT)"])
    run(capsys, ["exec", db_path, "INSERT INTO t VALUES (1)"])
    run(capsys, ["exec", db_path, "INSERT INTO t VALUES (2)"])
    code, out, _ = run(capsys, ["exec", db_path, "SELECT * FROM t"])
    assert code == 0
    assert "(2 row(s))" in out


def test_exec_error_exits_nonzero(tmp_path, capsys):
    db_path = str(tmp_path / "db.json")
    code, _, err = run(capsys, ["exec", db_path, "SELECT * FROM nope"])
    assert code == 1
    assert "error:" in err


def test_exec_syntax_error_exits_cleanly(tmp_path, capsys):
    db_path = str(tmp_path / "db.json")
    code, _, _ = run(capsys, ["exec", db_path, "NOT VALID SQL"])
    assert code == 1


def test_exec_null_value_prints_empty_cell(tmp_path, capsys):
    db_path = str(tmp_path / "db.json")
    run(capsys, ["exec", db_path, "CREATE TABLE t (a INT, b INT)"])
    run(capsys, ["exec", db_path, "INSERT INTO t (a) VALUES (1)"])
    code, out, _ = run(capsys, ["exec", db_path, "SELECT * FROM t"])
    assert code == 0
    assert "1\t\n" in out or out.strip().endswith("1\t")


def test_exec_script_with_explicit_transaction_commit(tmp_path, capsys):
    db_path = str(tmp_path / "db.json")
    run(capsys, ["exec", db_path, "CREATE TABLE t (id INT)"])
    code, out, _ = run(
        capsys,
        ["exec", db_path, "BEGIN; INSERT INTO t VALUES (1); INSERT INTO t VALUES (2); COMMIT;"],
    )
    assert code == 0
    code, out, _ = run(capsys, ["exec", db_path, "SELECT * FROM t"])
    assert "(2 row(s))" in out


def test_exec_script_rollback_leaves_db_unchanged(tmp_path, capsys):
    db_path = str(tmp_path / "db.json")
    run(capsys, ["exec", db_path, "CREATE TABLE t (id INT)"])
    run(capsys, ["exec", db_path, "BEGIN; INSERT INTO t VALUES (1); ROLLBACK;"])
    code, out, _ = run(capsys, ["exec", db_path, "SELECT * FROM t"])
    assert "(0 row(s))" in out


def test_exec_script_left_open_transaction_errors_and_does_not_save(tmp_path, capsys):
    db_path = str(tmp_path / "db.json")
    run(capsys, ["exec", db_path, "CREATE TABLE t (id INT)"])
    code, _, err = run(capsys, ["exec", db_path, "BEGIN; INSERT INTO t VALUES (1);"])
    assert code == 1
    assert "transaction open" in err
    code, out, _ = run(capsys, ["exec", db_path, "SELECT * FROM t"])
    assert "(0 row(s))" in out


def test_exec_script_failure_mid_script_does_not_save_anything(tmp_path, capsys):
    db_path = str(tmp_path / "db.json")
    run(capsys, ["exec", db_path, "CREATE TABLE t (id INT)"])
    code, _, err = run(
        capsys, ["exec", db_path, "INSERT INTO t VALUES (1); SELECT * FROM nope;"]
    )
    assert code == 1
    assert "error:" in err
    code, out, _ = run(capsys, ["exec", db_path, "SELECT * FROM t"])
    assert "(0 row(s))" in out


def test_shell_transaction_rollback(tmp_path, capsys, monkeypatch):
    db_path = str(tmp_path / "db.json")
    run(capsys, ["exec", db_path, "CREATE TABLE t (id INT)"])

    lines = iter(["BEGIN;", "INSERT INTO t VALUES (1);", "ROLLBACK;", "quit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))
    code, _, _ = run(capsys, ["shell", db_path])
    assert code == 0

    code, out, _ = run(capsys, ["exec", db_path, "SELECT * FROM t"])
    assert "(0 row(s))" in out


def test_shell_transaction_commit(tmp_path, capsys, monkeypatch):
    db_path = str(tmp_path / "db.json")
    run(capsys, ["exec", db_path, "CREATE TABLE t (id INT)"])

    lines = iter(["BEGIN;", "INSERT INTO t VALUES (1);", "COMMIT;", "quit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))
    code, _, _ = run(capsys, ["shell", db_path])
    assert code == 0

    code, out, _ = run(capsys, ["exec", db_path, "SELECT * FROM t"])
    assert "(1 row(s))" in out


def test_shell_exit_with_open_transaction_warns_and_does_not_save(tmp_path, capsys, monkeypatch):
    db_path = str(tmp_path / "db.json")
    run(capsys, ["exec", db_path, "CREATE TABLE t (id INT)"])

    lines = iter(["BEGIN;", "INSERT INTO t VALUES (1);", "quit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))
    code, out, _ = run(capsys, ["shell", db_path])
    assert code == 0
    assert "open transaction" in out

    code, out, _ = run(capsys, ["exec", db_path, "SELECT * FROM t"])
    assert "(0 row(s))" in out


def test_version(capsys):
    code, out, _ = run(capsys, ["--version"])
    assert code == 0
    assert "0.1.0" in out or "0.1" in out
