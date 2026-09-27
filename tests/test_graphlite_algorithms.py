import pytest

from graphlite.algorithms import connected_components, shortest_path
from graphlite.model import Graph, GraphError


def build_line_graph():
    g = Graph()
    for n in ("a", "b", "c", "d"):
        g.add_node(n)
    g.add_edge("e1", "a", "b", "NEXT")
    g.add_edge("e2", "b", "c", "NEXT")
    g.add_edge("e3", "c", "d", "NEXT")
    return g


def test_shortest_path_basic():
    g = build_line_graph()
    assert shortest_path(g, "a", "d") == ["a", "b", "c", "d"]


def test_shortest_path_same_node():
    g = build_line_graph()
    assert shortest_path(g, "a", "a") == ["a"]


def test_shortest_path_unreachable():
    g = build_line_graph()
    g.add_node("isolated")
    assert shortest_path(g, "a", "isolated") is None


def test_shortest_path_unknown_node_raises():
    g = build_line_graph()
    with pytest.raises(GraphError):
        shortest_path(g, "a", "nope")


def test_shortest_path_prefers_shorter_route():
    g = Graph()
    for n in ("a", "b", "c", "d"):
        g.add_node(n)
    g.add_edge("e1", "a", "b", "NEXT")
    g.add_edge("e2", "b", "d", "NEXT")
    g.add_edge("e3", "a", "c", "NEXT")
    g.add_edge("e4", "c", "d", "NEXT")
    g.add_edge("e5", "a", "d", "SHORTCUT")
    path = shortest_path(g, "a", "d")
    assert path == ["a", "d"]


def test_shortest_path_filtered_by_edge_type():
    g = Graph()
    for n in ("a", "b", "c"):
        g.add_node(n)
    g.add_edge("e1", "a", "b", "KNOWS")
    g.add_edge("e2", "b", "c", "LIKES")
    assert shortest_path(g, "a", "c", edge_type="KNOWS") is None
    assert shortest_path(g, "a", "b", edge_type="KNOWS") == ["a", "b"]


def test_connected_components_single_component():
    g = build_line_graph()
    components = connected_components(g)
    assert components == [["a", "b", "c", "d"]]


def test_connected_components_multiple():
    g = Graph()
    for n in ("a", "b", "x", "y", "z"):
        g.add_node(n)
    g.add_edge("e1", "a", "b", "KNOWS")
    g.add_edge("e2", "x", "y", "KNOWS")
    components = connected_components(g)
    assert components == [["a", "b"], ["x", "y"], ["z"]]


def test_connected_components_treats_direction_as_undirected():
    g = Graph()
    g.add_node("a")
    g.add_node("b")
    g.add_edge("e1", "b", "a", "KNOWS")
    assert connected_components(g) == [["a", "b"]]
