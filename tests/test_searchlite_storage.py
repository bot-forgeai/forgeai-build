from searchlite.index import Index
from searchlite.storage import load_index, load_or_new_index, save_index


def test_save_and_load_round_trip(tmp_path):
    path = str(tmp_path / "idx.json")
    index = Index()
    index.add_document("a", "hello world")
    save_index(index, path)
    loaded = load_index(path)
    assert loaded.doc_count == 1
    assert loaded.search("hello")[0][0] == "a"


def test_load_or_new_index_missing_file_returns_empty(tmp_path):
    path = str(tmp_path / "missing.json")
    index = load_or_new_index(path)
    assert index.doc_count == 0


def test_save_index_is_atomic_and_leaves_no_temp_file(tmp_path, monkeypatch):
    import json
    path = tmp_path / "i.json"
    idx = Index()
    idx.add_document("a", "alpha text")
    save_index(idx, str(path))
    before = path.read_text()

    def boom(*a, **kw):
        raise RuntimeError("disk full")

    monkeypatch.setattr(json, "dump", boom)
    try:
        save_index(idx, str(path))
    except RuntimeError:
        pass
    assert path.read_text() == before  # old index intact
    assert [p.name for p in tmp_path.iterdir()] == ["i.json"]
