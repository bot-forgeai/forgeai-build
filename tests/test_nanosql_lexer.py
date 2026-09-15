import pytest

from nanosql.lexer import LexError, Token, tokenize


def kinds_values(tokens):
    return [(t.kind, t.value) for t in tokens]


def test_tokenize_keywords_and_ident():
    tokens = tokenize("SELECT * FROM users")
    assert kinds_values(tokens) == [
        ("KEYWORD", "SELECT"),
        ("PUNCT", "*"),
        ("KEYWORD", "FROM"),
        ("IDENT", "users"),
        ("EOF", None),
    ]


def test_tokenize_numbers():
    tokens = tokenize("1 2.5 100")
    assert kinds_values(tokens)[:3] == [("NUMBER", 1), ("NUMBER", 2.5), ("NUMBER", 100)]
    assert isinstance(tokens[0].value, int)
    assert isinstance(tokens[1].value, float)


def test_tokenize_string_literal():
    tokens = tokenize("'hello world'")
    assert tokens[0] == Token("STRING", "hello world")


def test_tokenize_string_with_escaped_quote():
    tokens = tokenize("'it''s here'")
    assert tokens[0] == Token("STRING", "it's here")


def test_tokenize_operators():
    tokens = tokenize("a >= 1 AND b <> 2")
    values = [t.value for t in tokens if t.kind == "OP"]
    assert values == [">=", "!="]


def test_tokenize_unterminated_string_raises():
    with pytest.raises(LexError):
        tokenize("'unterminated")


def test_tokenize_unexpected_char_raises():
    with pytest.raises(LexError):
        tokenize("SELECT # FROM t")


def test_tokenize_punctuation():
    tokens = tokenize("(a, b);")
    kinds = [t.value for t in tokens if t.kind == "PUNCT"]
    assert kinds == ["(", ",", ")", ";"]
