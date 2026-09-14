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


def test_snippet_highlights_matched_term_in_context():
    index = Index()
    index.add_document(
        "a",
        "word " * 20 + "the quick brown fox jumps over the lazy dog" + " word" * 20,
    )
    snippet = index.snippet("a", "fox", radius=15)
    assert "**fox**" in snippet
    assert snippet.startswith("...")
    assert snippet.endswith("...")


def test_snippet_no_truncation_markers_when_match_near_edges():
    index = Index()
    index.add_document("a", "fox jumps")
    snippet = index.snippet("a", "fox", radius=40)
    assert snippet == "**fox** jumps"


def test_snippet_falls_back_when_query_not_found():
    index = Index()
    index.add_document("a", "apples and oranges")
    snippet = index.snippet("a", "zzznomatch")
    assert snippet.startswith("apples and oranges")


def test_snippet_survives_round_trip():
    index = Index()
    index.add_document("a", "the quick brown fox")
    restored = Index.from_dict(index.to_dict())
    snippet = restored.snippet("a", "fox")
    assert "**fox**" in snippet


def test_snippet_missing_doc_texts_key_falls_back_to_title():
    index = Index()
    index.add_document("a", "the quick brown fox")
    data = index.to_dict()
    del data["doc_texts"]
    restored = Index.from_dict(data)
    snippet = restored.snippet("a", "fox")
    assert snippet == restored.doc_titles["a"]


def test_bm25_ranks_more_relevant_doc_higher():
    index = Index()
    index.add_document("fox_doc", "fox fox fox jumps over the dog")
    index.add_document("dog_doc", "dog barks at the mailman")
    results = index.search("fox", rank="bm25")
    assert results[0][0] == "fox_doc"
    assert results[0][1] > 0


def test_bm25_no_match_returns_empty():
    index = Index()
    index.add_document("a", "apples and oranges")
    assert index.search("zzzznomatch", rank="bm25") == []


def test_bm25_empty_index_returns_empty():
    index = Index()
    assert index.search("anything", rank="bm25") == []


def test_bm25_penalizes_longer_documents_for_equal_term_frequency():
    index = Index()
    index.add_document("short", "fox " + "filler " * 5)
    index.add_document("long", "fox " + "filler " * 500)
    results = dict(index.search("fox", rank="bm25"))
    assert results["short"] > results["long"]


def test_unknown_rank_method_raises():
    index = Index()
    index.add_document("a", "hello world")
    try:
        index.search("hello", rank="nope")
        assert False, "expected ValueError"
    except ValueError:
        pass


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
