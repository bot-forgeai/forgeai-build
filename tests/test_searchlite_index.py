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


def test_remove_document_clears_phrase_positions():
    index = Index()
    index.add_document("a", "quick brown fox")
    index.remove_document("a")
    assert index.search_phrase("quick brown fox") == []


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


def test_search_phrase_matches_exact_sequence():
    index = Index()
    index.add_document("a", "the quick brown fox jumps over the lazy dog")
    index.add_document("b", "a fox that is quick and brown but never jumps")
    results = index.search_phrase("quick brown fox")
    assert [doc_id for doc_id, _ in results] == ["a"]


def test_search_phrase_rejects_out_of_order_terms():
    index = Index()
    index.add_document("a", "brown quick fox")
    assert index.search_phrase("quick brown fox") == []


def test_search_phrase_single_term_matches_postings():
    index = Index()
    index.add_document("a", "fox fox fox")
    index.add_document("b", "fox")
    results = index.search_phrase("fox")
    assert results[0] == ("a", 3)


def test_search_phrase_no_match_returns_empty():
    index = Index()
    index.add_document("a", "apples and oranges")
    assert index.search_phrase("zzznomatch phrase") == []


def test_search_phrase_counts_multiple_occurrences():
    index = Index()
    index.add_document("a", "red fox brown fox red fox brown fox")
    results = dict(index.search_phrase("red fox"))
    assert results["a"] == 2


def test_search_phrase_respects_top_k():
    index = Index()
    for i in range(5):
        index.add_document(f"doc{i}", "shared phrase term")
    results = index.search_phrase("shared phrase", top_k=2)
    assert len(results) == 2


def test_search_phrase_survives_round_trip():
    index = Index()
    index.add_document("a", "the quick brown fox")
    restored = Index.from_dict(index.to_dict())
    results = restored.search_phrase("quick brown fox")
    assert [doc_id for doc_id, _ in results] == ["a"]


def test_search_phrase_missing_positions_key_finds_nothing():
    index = Index()
    index.add_document("a", "the quick brown fox")
    data = index.to_dict()
    del data["positions"]
    restored = Index.from_dict(data)
    assert restored.search_phrase("quick brown fox") == []


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


def test_search_minus_term_excludes_docs():
    index = Index()
    index.add_document("a", "sd card wear and swap")
    index.add_document("b", "sd card wear levelling")
    assert [d for d, _ in index.search("card -swap")] == ["b"]
    assert [d for d, _ in index.search("card -swap", rank="bm25")] == ["b"]


def test_search_inner_hyphen_is_not_exclusion():
    index = Index()
    index.add_document("a", "sd-card storage")
    assert [d for d, _ in index.search("sd-card")] == ["a"]


def test_search_quoted_phrase_requires_consecutive_terms():
    index = Index()
    index.add_document("a", "sd card wear")
    index.add_document("b", "credit card and sd reader")
    assert [d for d, _ in index.search('"sd card"')] == ["a"]
    assert [d for d, _ in index.search('"sd card" -wear')] == []
    assert len(index.search("card")) == 2


def test_search_trailing_star_matches_term_prefix():
    index = Index()
    index.add_document("a", "compressor tuning")
    index.add_document("b", "compression ratio")
    index.add_document("c", "unrelated text")
    ids = [d for d, _ in index.search("compress*")]
    assert sorted(ids) == ["a", "b"]


def test_search_prefix_without_match_returns_nothing():
    index = Index()
    index.add_document("a", "hello world")
    assert index.search("zzz*") == []


def test_snippet_expands_wildcard_and_skips_exclusion():
    index = Index()
    index.add_document("a", "the swap device handles compression of pages quickly")
    snippet = index.snippet("a", "compress* -swap", radius=60)
    assert "**compression**" in snippet
    assert "**swap**" not in snippet


def test_snippet_ignores_quote_characters():
    index = Index()
    index.add_document("a", "wear on the sd card grows over time")
    assert "**card**" in index.snippet("a", '"sd card"', radius=30)


def test_search_plus_term_is_required():
    idx = Index()
    idx.add_document("a", "zram swap compression")
    idx.add_document("b", "zram only here")
    idx.add_document("c", "swap swap swap file")
    assert {d for d, _ in idx.search("zram swap")} == {"a", "b", "c"}
    assert [d for d, _ in idx.search("+zram swap")] == ["a", "b"]
    assert [d for d, _ in idx.search("+zram +swap")] == ["a"]
    assert idx.search("+nosuchword zram") == []
