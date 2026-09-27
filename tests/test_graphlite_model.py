import pytest

from graphlite.model import Graph, GraphError


def test_add_and_query_node():
    g = Graph()
    g.add_node("a", labels=["Person"], props={"name": "Ada"})
    assert g.has_node("a")
    assert g.nodes["a"]["labels"] == ["Person"]
    assert g.nodes["a"]["props"]["name"] == "Ada"


def test_add_node_duplicate_raises():
    g = Graph()
    g.add_node("a")
    with pytest.raises(GraphError):
        g.add_node("a")


def test_add_edge_requires_existing_nodes():
    g = Graph()
    g.add_node("a")
    with pytest.raises(GraphError):
        g.add_edge("e1", "a", "b", "KNOWS")


def test_add_edge_and_neighbors():
    g = Graph()
    g.add_node("a")
    g.add_node("b")
    g.add_edge("e1", "a", "b", "KNOWS")
    assert g.neighbors("a", direction="out") == ["b"]
    assert g.neighbors("b", direction="in") == ["a"]
    assert g.neighbors("b", direction="out") == []


def test_neighbors_filtered_by_type():
    g = Graph()
    g.add_node("a")
    g.add_node("b")
    g.add_node("c")
    g.add_edge("e1", "a", "b", "KNOWS")
    g.add_edge("e2", "a", "c", "LIKES")
    assert g.neighbors("a", edge_type="KNOWS") == ["b"]
    assert g.neighbors("a", edge_type="LIKES") == ["c"]
    assert set(g.neighbors("a")) == {"b", "c"}


def test_remove_edge():
    g = Graph()
    g.add_node("a")
    g.add_node("b")
    g.add_edge("e1", "a", "b", "KNOWS")
    g.remove_edge("e1")
    assert g.neighbors("a") == []
    assert "e1" not in g.edges


def test_remove_edge_unknown_raises():
    g = Graph()
    with pytest.raises(GraphError):
        g.remove_edge("nope")


def test_remove_node_drops_incident_edges():
    g = Graph()
    g.add_node("a")
    g.add_node("b")
    g.add_node("c")
    g.add_edge("e1", "a", "b", "KNOWS")
    g.add_edge("e2", "b", "c", "KNOWS")
    g.remove_node("b")
    assert "b" not in g.nodes
    assert "e1" not in g.edges
    assert "e2" not in g.edges
    assert g.neighbors("a") == []
    assert g.neighbors("c", direction="in") == []


def test_remove_node_unknown_raises():
    g = Graph()
    with pytest.raises(GraphError):
        g.remove_node("nope")


def test_to_dict_from_dict_round_trip():
    g = Graph()
    g.add_node("a", labels=["Person"], props={"name": "Ada"})
    g.add_node("b", labels=["Person"], props={"name": "Bob"})
    g.add_edge("e1", "a", "b", "KNOWS", props={"since": 2020})
    data = g.to_dict()
    restored = Graph.from_dict(data)
    assert restored.nodes == g.nodes
    assert restored.edges == g.edges
    assert restored.neighbors("a") == ["b"]


def test_out_edges():
    g = Graph()
    g.add_node("a")
    g.add_node("b")
    g.add_edge("e1", "a", "b", "KNOWS")
    edges = list(g.out_edges("a"))
    assert len(edges) == 1
    assert edges[0][0] == "e1"
    assert edges[0][1]["to"] == "b"
