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
