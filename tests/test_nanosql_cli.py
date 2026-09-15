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
