from searchlite.tokenize import tokenize


def test_lowercases_and_splits():
    assert tokenize("Hello, World!") == ["hello", "world"]


def test_strips_stopwords_by_default():
    assert tokenize("the cat is on the mat") == ["cat", "mat"]


def test_keeps_stopwords_when_disabled():
    assert tokenize("the cat", stopwords=False) == ["the", "cat"]


def test_numbers_are_tokens():
    assert tokenize("python3 v2 release") == ["python3", "v2", "release"]


def test_empty_string():
    assert tokenize("") == []
