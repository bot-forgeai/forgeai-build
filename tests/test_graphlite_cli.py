import json

import pytest

from graphlite.__main__ import main


def run(capsys, argv):
    try:
        main(argv)
        code = 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_init_creates_file(tmp_path, capsys):
    db_path = str(tmp_path / "g.json")
    code, out, _ = run(capsys, ["init", db_path])
    assert code == 0
    assert "initialized" in out


def test_init_twice_errors(tmp_path, capsys):
    db_path = str(tmp_path / "g.json")
    run(capsys, ["init", db_path])
    code, _, err = run(capsys, ["init", db_path])
    assert code == 1
    assert "already exists" in err


def test_add_node_and_edge_then_query(tmp_path, capsys):
    db_path = str(tmp_path / "g.json")
    run(capsys, ["init", db_path])
    code, _, _ = run(capsys, ["add-node", db_path, "ada", "--label", "Person", "--prop", "name=Ada", "--prop", "age=36"])
    assert code == 0
    run(capsys, ["add-node", db_path, "bob", "--label", "Person", "--prop", "name=Bob"])
    code, _, _ = run(capsys, ["add-edge", db_path, "e1", "ada", "bob", "KNOWS"])
    assert code == 0
    code, out, _ = run(capsys, ["query", db_path, "MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name, b.name"])
    assert code == 0
    assert "Ada" in out and "Bob" in out
    assert "(1 row(s))" in out


def test_add_edge_missing_node_errors(tmp_path, capsys):
    db_path = str(tmp_path / "g.json")
    run(capsys, ["init", db_path])
    code, _, err = run(capsys, ["add-edge", db_path, "e1", "a", "b", "KNOWS"])
    assert code == 1
    assert "does not exist" in err


def test_remove_node_and_edge(tmp_path, capsys):
    db_path = str(tmp_path / "g.json")
    run(capsys, ["init", db_path])
    run(capsys, ["add-node", db_path, "a"])
    run(capsys, ["add-node", db_path, "b"])
    run(capsys, ["add-edge", db_path, "e1", "a", "b", "KNOWS"])
    code, out, _ = run(capsys, ["remove-edge", db_path, "e1"])
    assert code == 0
    code, out, _ = run(capsys, ["remove-node", db_path, "a"])
    assert code == 0
    code, out, _ = run(capsys, ["stats", db_path])
    assert "nodes: 1" in out
    assert "edges: 0" in out


def test_query_persists_no_state_change(tmp_path, capsys):
    db_path = str(tmp_path / "g.json")
    run(capsys, ["init", db_path])
    run(capsys, ["add-node", db_path, "a"])
    code, out, _ = run(capsys, ["query", db_path, "MATCH (a)-[]->(b) RETURN a"])
    assert code == 0
    assert "(0 rows)" in out


def test_query_syntax_error_exits_nonzero(tmp_path, capsys):
    db_path = str(tmp_path / "g.json")
    run(capsys, ["init", db_path])
    code, _, err = run(capsys, ["query", db_path, "MATCH bogus"])
    assert code == 1
    assert "error:" in err


def test_query_format_json(tmp_path, capsys):
    db_path = str(tmp_path / "g.json")
    run(capsys, ["init", db_path])
    run(capsys, ["add-node", db_path, "ada", "--label", "Person", "--prop", "name=Ada"])
    run(capsys, ["add-node", db_path, "bob", "--label", "Person", "--prop", "name=Bob"])
    run(capsys, ["add-edge", db_path, "e1", "ada", "bob", "KNOWS"])
    code, out, _ = run(
        capsys, ["query", db_path, "MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name, b.name", "--format", "json"]
    )
    assert code == 0
    rows = json.loads(out)
    assert rows == [{"a.name": "Ada", "b.name": "Bob"}]


def test_query_format_json_empty(tmp_path, capsys):
    db_path = str(tmp_path / "g.json")
    run(capsys, ["init", db_path])
    run(capsys, ["add-node", db_path, "a"])
    code, out, _ = run(capsys, ["query", db_path, "MATCH (a)-[]->(b) RETURN a", "--format", "json"])
    assert code == 0
    assert json.loads(out) == []


def test_query_format_json_returns_whole_node(tmp_path, capsys):
    db_path = str(tmp_path / "g.json")
    run(capsys, ["init", db_path])
    run(capsys, ["add-node", db_path, "ada", "--label", "Person", "--prop", "name=Ada"])
    code, out, _ = run(capsys, ["query", db_path, "MATCH (a:Person) RETURN a", "--format", "json"])
    assert code == 0
    rows = json.loads(out)
    assert len(rows) == 1
    assert rows[0]["a"]["id"] == "ada"
    assert rows[0]["a"]["labels"] == ["Person"]
    assert rows[0]["a"]["props"] == {"name": "Ada"}


def test_shortest_path(tmp_path, capsys):
    db_path = str(tmp_path / "g.json")
    run(capsys, ["init", db_path])
    for n in ("a", "b", "c"):
        run(capsys, ["add-node", db_path, n])
    run(capsys, ["add-edge", db_path, "e1", "a", "b", "NEXT"])
    run(capsys, ["add-edge", db_path, "e2", "b", "c", "NEXT"])
    code, out, _ = run(capsys, ["shortest-path", db_path, "a", "c"])
    assert code == 0
    assert "a -> b -> c" in out


def test_shortest_path_unreachable_exits_nonzero(tmp_path, capsys):
    db_path = str(tmp_path / "g.json")
    run(capsys, ["init", db_path])
    run(capsys, ["add-node", db_path, "a"])
    run(capsys, ["add-node", db_path, "b"])
    code, out, _ = run(capsys, ["shortest-path", db_path, "a", "b"])
    assert code == 1
    assert "no path" in out


def test_components(tmp_path, capsys):
    db_path = str(tmp_path / "g.json")
    run(capsys, ["init", db_path])
    run(capsys, ["add-node", db_path, "a"])
    run(capsys, ["add-node", db_path, "b"])
    run(capsys, ["add-node", db_path, "c"])
    run(capsys, ["add-edge", db_path, "e1", "a", "b", "KNOWS"])
    code, out, _ = run(capsys, ["components", db_path])
    assert code == 0
    assert "(2 component(s))" in out


def test_version_flag(capsys):
    code, out, _ = run(capsys, ["--version"])
    assert code == 0
    assert out.strip()
