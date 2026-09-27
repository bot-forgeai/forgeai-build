import pytest

from graphlite.lexer import LexError, Token, tokenize


def test_tokenize_pattern():
    tokens = tokenize("MATCH (a:Person)-[:KNOWS]->(b)")
    kinds_values = [(t.kind, t.value) for t in tokens]
    assert kinds_values[0] == ("KEYWORD", "MATCH")
    assert Token("SYM", "(") in tokens
    assert Token("SYM", "->") in tokens
    assert Token("IDENT", "Person") in tokens
    assert tokens[-1] == Token("EOF", None)


def test_tokenize_string_and_number():
    tokens = tokenize("WHERE a.age > 30 AND b.name = 'Bob'")
    values = [t.value for t in tokens]
    assert 30 in values
    assert "Bob" in values


def test_tokenize_unterminated_string_raises():
    with pytest.raises(LexError):
        tokenize("'unterminated")


def test_tokenize_unexpected_char_raises():
    with pytest.raises(LexError):
        tokenize("MATCH @")
