import pytest

from toylang.lexer import tokenize, ToylangSyntaxError


def types(tokens):
    return [t.type for t in tokens]


def test_numbers_int_and_float():
    tokens = tokenize("1 2.5 10")
    assert [t.value for t in tokens[:3]] == [1, 2.5, 10]
    assert types(tokens) == ["NUMBER", "NUMBER", "NUMBER", "EOF"]


def test_string_with_escapes():
    tokens = tokenize(r'"hi\nthere\t\"quoted\""')
    assert tokens[0].value == 'hi\nthere\t"quoted"'


def test_keywords_vs_identifiers():
    tokens = tokenize("let x = if y else true false nil and or not")
    assert types(tokens) == [
        "LET", "IDENT", "=", "IF", "IDENT", "ELSE",
        "TRUE", "FALSE", "NIL", "AND", "OR", "NOT", "EOF",
    ]


def test_symbols_longest_match_first():
    tokens = tokenize("== != <= >= = < > + - * / %")
    assert types(tokens) == [
        "==", "!=", "<=", ">=", "=", "<", ">", "+", "-", "*", "/", "%", "EOF",
    ]


def test_comments_ignored():
    tokens = tokenize("let x = 1; # a comment\nlet y = 2;")
    assert types(tokens).count("LET") == 2


def test_unterminated_string_raises():
    with pytest.raises(ToylangSyntaxError):
        tokenize('"never closed')


def test_unexpected_character_raises():
    with pytest.raises(ToylangSyntaxError):
        tokenize("let x = @;")


def test_line_tracking():
    tokens = tokenize("let x = 1;\nlet y = 2;")
    let_tokens = [t for t in tokens if t.type == "LET"]
    assert let_tokens[0].line == 1
    assert let_tokens[1].line == 2


def test_brackets_tokenized():
    tokens = tokenize("[1, 2]")
    assert types(tokens) == ["[", "NUMBER", ",", "NUMBER", "]", "EOF"]
