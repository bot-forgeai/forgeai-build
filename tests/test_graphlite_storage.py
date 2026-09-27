from graphlite.model import Graph
from graphlite.storage import load, save


def test_load_missing_file_returns_empty_graph(tmp_path):
    g = load(str(tmp_path / "nope.json"))
    assert g.nodes == {}
    assert g.edges == {}


def test_save_and_load_round_trip(tmp_path):
    path = str(tmp_path / "g.json")
    g = Graph()
    g.add_node("a", labels=["Person"], props={"name": "Ada"})
    g.add_node("b")
    g.add_edge("e1", "a", "b", "KNOWS")
    save(g, path)
    loaded = load(path)
    assert loaded.nodes["a"]["props"]["name"] == "Ada"
    assert loaded.neighbors("a") == ["b"]


def test_save_is_atomic_no_leftover_temp_files(tmp_path):
    path = str(tmp_path / "g.json")
    save(Graph(), path)
    leftovers = [p for p in tmp_path.iterdir() if p.name != "g.json"]
    assert leftovers == []
