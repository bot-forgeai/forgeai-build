import pytest

from graphlite.model import Graph
from graphlite.query import Condition, QueryError, execute, parse


def build_graph():
    g = Graph()
    g.add_node("ada", labels=["Person"], props={"name": "Ada", "age": 36})
    g.add_node("bob", labels=["Person"], props={"name": "Bob", "age": 25})
    g.add_node("acme", labels=["Company"], props={"name": "Acme"})
    g.add_edge("e1", "ada", "bob", "KNOWS", props={"since": 2020})
    g.add_edge("e2", "ada", "acme", "WORKS_AT")
    g.add_edge("e3", "bob", "acme", "WORKS_AT")
    return g


def test_parse_basic_query():
    q = parse("MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name, b.name")
    assert q.left.var == "a"
    assert q.left.label == "Person"
    assert q.edge_type == "KNOWS"
    assert q.right.var == "b"
    assert [item.prop for item in q.returns] == ["name", "name"]


def test_parse_untyped_edge_and_unlabeled_nodes():
    q = parse("MATCH (a)-[]->(b) RETURN a, b")
    assert q.left.label is None
    assert q.edge_type is None
    assert q.returns[0].prop is None


def test_parse_where_and_limit():
    q = parse("MATCH (a:Person)-[:KNOWS]->(b:Person) WHERE a.age > 30 AND b.age < 40 RETURN a.name LIMIT 5")
    assert len(q.where) == 2
    assert q.where[0].var == "a" and q.where[0].op == ">" and q.where[0].value == 30
    assert q.limit == 5


def test_parse_syntax_error_raises():
    with pytest.raises(QueryError):
        parse("MATCH (a Person)-[:KNOWS]->(b) RETURN a")


def test_execute_returns_matching_pairs():
    g = build_graph()
    q = parse("MATCH (a:Person)-[:WORKS_AT]->(b:Company) RETURN a.name, b.name")
    rows = execute(g, q)
    names = sorted(r["a.name"] for r in rows)
    assert names == ["Ada", "Bob"]
    assert all(r["b.name"] == "Acme" for r in rows)


def test_execute_filters_by_where():
    g = build_graph()
    q = parse("MATCH (a:Person)-[:WORKS_AT]->(b:Company) WHERE a.age > 30 RETURN a.name")
    rows = execute(g, q)
    assert [r["a.name"] for r in rows] == ["Ada"]


def test_execute_untyped_edge_matches_any_type():
    g = build_graph()
    q = parse("MATCH (a:Person)-[]->(b) RETURN a.name")
    rows = execute(g, q)
    assert len(rows) == 3  # ada->bob, ada->acme, bob->acme


def test_execute_limit():
    g = build_graph()
    q = parse("MATCH (a:Person)-[]->(b) RETURN a.name LIMIT 1")
    rows = execute(g, q)
    assert len(rows) == 1


def test_execute_return_whole_node():
    g = build_graph()
    q = parse("MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN b")
    rows = execute(g, q)
    assert rows[0]["b"]["id"] == "bob"
    assert rows[0]["b"]["props"]["name"] == "Bob"


def test_execute_no_matches_returns_empty():
    g = build_graph()
    q = parse("MATCH (a:Company)-[:KNOWS]->(b:Person) RETURN a")
    assert execute(g, q) == []


def test_execute_unbound_variable_in_where_raises():
    g = build_graph()
    q = parse("MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name")
    q.where.append(Condition("c", "age", "=", 1))
    with pytest.raises(QueryError):
        execute(g, q)
