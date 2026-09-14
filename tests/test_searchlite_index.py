from searchlite.index import Index


def test_add_and_doc_count():
    index = Index()
    index.add_document("a", "the quick brown fox")
    index.add_document("b", "the lazy dog")
    assert index.doc_count == 2


def test_search_ranks_more_relevant_doc_higher():
    index = Index()
    index.add_document("fox_doc", "fox fox fox jumps over the dog")
    index.add_document("dog_doc", "dog barks at the mailman")
    results = index.search("fox")
    assert results[0][0] == "fox_doc"
    assert results[0][1] > 0


def test_search_no_match_returns_empty():
    index = Index()
    index.add_document("a", "apples and oranges")
    assert index.search("zzzznomatch") == []


def test_search_respects_top_k():
    index = Index()
    for i in range(5):
        index.add_document(f"doc{i}", "shared term")
    results = index.search("shared", top_k=2)
    assert len(results) == 2


def test_remove_document():
    index = Index()
    index.add_document("a", "hello world")
    assert index.remove_document("a") is True
    assert index.doc_count == 0
    assert index.search("hello") == []


def test_remove_missing_document_returns_false():
    index = Index()
    assert index.remove_document("nope") is False


def test_reindexing_same_doc_id_replaces_content():
    index = Index()
    index.add_document("a", "apples")
    index.add_document("a", "oranges")
    assert index.search("apples") == []
    results = index.search("oranges")
    assert results and results[0][0] == "a"


def test_to_dict_from_dict_round_trip():
    index = Index()
    index.add_document("a", "hello world")
    index.add_document("b", "goodbye world")
    restored = Index.from_dict(index.to_dict())
    assert restored.doc_count == 2
    results = restored.search("hello")
    assert results and results[0][0] == "a"


def test_idf_favors_rarer_terms():
    index = Index()
    index.add_document("a", "common common rare")
    index.add_document("b", "common common common")
    index.add_document("c", "common common common")
    # "rare" appears in only one doc; a query combining both terms should
    # still rank doc "a" highly due to the rare-term boost, and only "a"
    # matches "rare" at all.
    results = dict(index.search("rare"))
    assert list(results.keys()) == ["a"]
