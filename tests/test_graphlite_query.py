import pytest

from graphlite.model import Graph
from graphlite.query import Condition, OrderItem, QueryError, execute, parse


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


def test_parse_where_or_precedence():
    q = parse(
        "MATCH (a:Person) WHERE a.age > 30 AND a.name = 'Ada' OR a.age < 10 RETURN a.name"
    )
    assert len(q.where_groups) == 2
    assert len(q.where_groups[0]) == 2
    assert len(q.where_groups[1]) == 1
    with pytest.raises(AttributeError):
        q.where


def test_parse_where_plain_and_still_returns_flat_where():
    q = parse("MATCH (a:Person) WHERE a.age > 30 RETURN a.name")
    assert q.where_groups == [q.where]


def test_execute_where_or_matches_either_group():
    g = build_graph()
    q = parse(
        "MATCH (a:Person) WHERE a.age > 100 OR a.age < 30 RETURN a.name"
    )
    rows = execute(g, q)
    assert rows == [{"a.name": "Bob"}]


def test_execute_where_or_of_ands():
    g = build_graph()
    q = parse(
        "MATCH (a:Person) WHERE a.age > 30 AND a.name = 'Ada' OR a.age < 30 AND a.name = 'Bob' "
        "RETURN a.name"
    )
    rows = execute(g, q)
    assert {r["a.name"] for r in rows} == {"Ada", "Bob"}


def test_execute_where_no_clause_matches_everything():
    g = build_graph()
    q = parse("MATCH (a:Person) RETURN a.name")
    assert q.where_groups == []
    rows = execute(g, q)
    assert {r["a.name"] for r in rows} == {"Ada", "Bob"}


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
    q.where_groups.append([Condition("c", "age", "=", 1)])
    with pytest.raises(QueryError):
        execute(g, q)


def test_parse_multi_hop_pattern():
    q = parse(
        "MATCH (a:Person)-[:KNOWS]->(b:Person)-[:WORKS_AT]->(c:Company) RETURN a.name, c.name"
    )
    assert [n.var for n in q.nodes] == ["a", "b", "c"]
    assert q.edge_types == ["KNOWS", "WORKS_AT"]


def test_execute_multi_hop_chain():
    g = build_graph()
    q = parse(
        "MATCH (a:Person)-[:KNOWS]->(b:Person)-[:WORKS_AT]->(c:Company) "
        "RETURN a.name, b.name, c.name"
    )
    rows = execute(g, q)
    assert len(rows) == 1
    assert rows[0] == {"a.name": "Ada", "b.name": "Bob", "c.name": "Acme"}


def test_execute_multi_hop_no_match_returns_empty():
    g = build_graph()
    q = parse(
        "MATCH (a:Company)-[:WORKS_AT]->(b:Person)-[:WORKS_AT]->(c:Company) RETURN a"
    )
    assert execute(g, q) == []


def test_execute_multi_hop_repeated_variable_constrains_same_node():
    g = build_graph()
    g.add_edge("e4", "bob", "ada", "KNOWS")
    q = parse("MATCH (a:Person)-[:KNOWS]->(b:Person)-[:KNOWS]->(a) RETURN a.name, b.name")
    rows = execute(g, q)
    # ada<->bob mutually KNOWS each other, so both role assignments match.
    pairs = sorted((r["a.name"], r["b.name"]) for r in rows)
    assert pairs == [("Ada", "Bob"), ("Bob", "Ada")]


def test_execute_multi_hop_limit():
    g = build_graph()
    g.add_node("carol", labels=["Person"], props={"name": "Carol", "age": 40})
    g.add_edge("e5", "carol", "ada", "KNOWS")
    unlimited = parse(
        "MATCH (a:Person)-[:KNOWS]->(b:Person)-[:WORKS_AT]->(c:Company) RETURN a.name"
    )
    assert len(execute(g, unlimited)) == 2  # carol->ada->acme and ada->bob->acme
    limited = parse(
        "MATCH (a:Person)-[:KNOWS]->(b:Person)-[:WORKS_AT]->(c:Company) RETURN a.name LIMIT 1"
    )
    assert len(execute(g, limited)) == 1


def test_parse_order_by_default_asc():
    q = parse("MATCH (a:Person) RETURN a.name ORDER BY a.age")
    assert len(q.order_by) == 1
    assert q.order_by[0].var == "a"
    assert q.order_by[0].prop == "age"
    assert q.order_by[0].descending is False


def test_parse_order_by_desc():
    q = parse("MATCH (a:Person) RETURN a.name ORDER BY a.age DESC")
    assert q.order_by[0].descending is True


def test_parse_order_by_multi_key():
    q = parse("MATCH (a:Person) RETURN a.name ORDER BY a.age DESC, a.name ASC")
    assert len(q.order_by) == 2
    assert q.order_by[0].descending is True
    assert q.order_by[1].descending is False


def test_execute_order_by_asc():
    g = build_graph()
    q = parse("MATCH (a:Person) RETURN a.name ORDER BY a.age")
    rows = execute(g, q)
    assert [r["a.name"] for r in rows] == ["Bob", "Ada"]


def test_execute_order_by_desc():
    g = build_graph()
    q = parse("MATCH (a:Person) RETURN a.name ORDER BY a.age DESC")
    rows = execute(g, q)
    assert [r["a.name"] for r in rows] == ["Ada", "Bob"]


def test_execute_order_by_then_limit():
    g = build_graph()
    q = parse("MATCH (a:Person) RETURN a.name ORDER BY a.age DESC LIMIT 1")
    rows = execute(g, q)
    assert [r["a.name"] for r in rows] == ["Ada"]


def test_execute_order_by_missing_property_sorts_last():
    g = build_graph()
    g.add_node("dave", labels=["Person"], props={"name": "Dave"})  # no age
    q = parse("MATCH (a:Person) RETURN a.name ORDER BY a.age")
    rows = execute(g, q)
    assert [r["a.name"] for r in rows] == ["Bob", "Ada", "Dave"]


def test_execute_order_by_missing_property_sorts_last_desc():
    g = build_graph()
    g.add_node("dave", labels=["Person"], props={"name": "Dave"})  # no age
    q = parse("MATCH (a:Person) RETURN a.name ORDER BY a.age DESC")
    rows = execute(g, q)
    assert [r["a.name"] for r in rows] == ["Ada", "Bob", "Dave"]


def test_execute_order_by_multi_key_sort():
    g = Graph()
    g.add_node("a1", labels=["Person"], props={"name": "Zed", "team": "A"})
    g.add_node("a2", labels=["Person"], props={"name": "Amy", "team": "A"})
    g.add_node("b1", labels=["Person"], props={"name": "Bea", "team": "B"})
    q = parse("MATCH (a:Person) RETURN a.name ORDER BY a.team ASC, a.name ASC")
    rows = execute(g, q)
    assert [r["a.name"] for r in rows] == ["Amy", "Zed", "Bea"]


def test_execute_order_by_unbound_variable_raises():
    g = build_graph()
    q = parse("MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name")
    q.order_by.append(OrderItem("c", "age"))
    with pytest.raises(QueryError):
        execute(g, q)


def build_chain_graph():
    """a -KNOWS-> b -KNOWS-> c -KNOWS-> d, plus a -LIKES-> e."""
    g = Graph()
    for n in "abcde":
        g.add_node(n, labels=["Person"], props={"name": n})
    g.add_edge("e1", "a", "b", "KNOWS")
    g.add_edge("e2", "b", "c", "KNOWS")
    g.add_edge("e3", "c", "d", "KNOWS")
    g.add_edge("e4", "a", "e", "LIKES")
    return g


def test_parse_variable_length_exact():
    q = parse("MATCH (a)-[:KNOWS*2]->(b) RETURN a")
    spec = q.edge_specs[0]
    assert spec.edge_type == "KNOWS"
    assert spec.min_hops == 2
    assert spec.max_hops == 2
    assert spec.is_variable


def test_parse_variable_length_range():
    q = parse("MATCH (a)-[:KNOWS*1..3]->(b) RETURN a")
    spec = q.edge_specs[0]
    assert spec.min_hops == 1
    assert spec.max_hops == 3


def test_parse_variable_length_open_upper():
    q = parse("MATCH (a)-[:KNOWS*2..]->(b) RETURN a")
    spec = q.edge_specs[0]
    assert spec.min_hops == 2
    assert spec.max_hops is None


def test_parse_variable_length_open_lower():
    q = parse("MATCH (a)-[:KNOWS*..2]->(b) RETURN a")
    spec = q.edge_specs[0]
    assert spec.min_hops == 1
    assert spec.max_hops == 2


def test_parse_variable_length_bad_hop_count_raises():
    with pytest.raises(QueryError):
        parse("MATCH (a)-[:KNOWS*x]->(b) RETURN a")


def test_parse_fixed_hop_is_not_variable():
    q = parse("MATCH (a)-[:KNOWS]->(b) RETURN a")
    assert not q.edge_specs[0].is_variable


def test_execute_variable_length_exact():
    g = build_chain_graph()
    q = parse("MATCH (a:Person)-[:KNOWS*2]->(b:Person) WHERE a.name = 'a' RETURN b.name")
    rows = execute(g, q)
    assert [r["b.name"] for r in rows] == ["c"]


def test_execute_variable_length_range():
    g = build_chain_graph()
    q = parse("MATCH (a:Person)-[:KNOWS*1..3]->(b:Person) WHERE a.name = 'a' RETURN b.name")
    rows = execute(g, q)
    assert [r["b.name"] for r in rows] == ["b", "c", "d"]


def test_execute_variable_length_open_upper():
    g = build_chain_graph()
    q = parse("MATCH (a:Person)-[:KNOWS*2..]->(b:Person) WHERE a.name = 'a' RETURN b.name")
    rows = execute(g, q)
    assert [r["b.name"] for r in rows] == ["c", "d"]


def test_execute_variable_length_open_lower():
    g = build_chain_graph()
    q = parse("MATCH (a:Person)-[:KNOWS*..2]->(b:Person) WHERE a.name = 'a' RETURN b.name")
    rows = execute(g, q)
    assert [r["b.name"] for r in rows] == ["b", "c"]


def test_execute_variable_length_untyped_matches_any_type():
    g = build_chain_graph()
    q = parse("MATCH (a:Person)-[*1..1]->(b:Person) WHERE a.name = 'a' RETURN b.name")
    rows = execute(g, q)
    assert sorted(r["b.name"] for r in rows) == ["b", "e"]


def test_execute_variable_length_respects_type_filter():
    g = build_chain_graph()
    q = parse("MATCH (a:Person)-[:LIKES*1..3]->(b:Person) WHERE a.name = 'a' RETURN b.name")
    rows = execute(g, q)
    assert [r["b.name"] for r in rows] == ["e"]


def test_execute_variable_length_no_infinite_loop_on_cycle():
    g = Graph()
    for n in "xyz":
        g.add_node(n, labels=["Person"], props={"name": n})
    g.add_edge("e1", "x", "y", "KNOWS")
    g.add_edge("e2", "y", "z", "KNOWS")
    g.add_edge("e3", "z", "x", "KNOWS")
    q = parse("MATCH (a:Person)-[:KNOWS*1..10]->(b:Person) WHERE a.name = 'x' RETURN b.name")
    rows = execute(g, q)
    # Simple paths only: x->y, x->y->z, x->y->z->x is not simple (repeats x).
    assert sorted(r["b.name"] for r in rows) == ["y", "z"]


def test_execute_variable_length_chained_with_fixed_hop():
    g = build_chain_graph()
    q = parse("MATCH (a:Person)-[:KNOWS*1..2]->(b:Person)-[:KNOWS]->(c:Person) WHERE a.name = 'a' RETURN b.name, c.name")
    rows = execute(g, q)
    assert [(r["b.name"], r["c.name"]) for r in rows] == [("b", "c"), ("c", "d")]


def test_lexer_hop_range_does_not_swallow_dots_as_a_float():
    from graphlite.lexer import tokenize

    tokens = [t for t in tokenize("*1..3") if t.kind != "EOF"]
    assert [(t.kind, t.value) for t in tokens] == [
        ("SYM", "*"),
        ("NUMBER", 1),
        ("SYM", "."),
        ("SYM", "."),
        ("NUMBER", 3),
    ]


def test_lexer_still_parses_float_literals():
    from graphlite.lexer import tokenize

    tokens = [t for t in tokenize("3.5") if t.kind != "EOF"]
    assert [(t.kind, t.value) for t in tokens] == [("NUMBER", 3.5)]
