"""Tokenizer for graphlite's MATCH/WHERE/RETURN query language."""

KEYWORDS = {"MATCH", "WHERE", "RETURN", "AND", "OR", "LIMIT", "TRUE", "FALSE"}

# Longer symbols must come before their prefixes (e.g. "->" before "-").
SYMBOLS = ["->", "<=", ">=", "!=", "=", "<", ">", "(", ")", "[", "]", ":", ",", ".", "-"]


class Token:
    def __init__(self, kind, value):
        self.kind = kind
        self.value = value

    def __repr__(self):
        return f"Token({self.kind!r}, {self.value!r})"

    def __eq__(self, other):
        return isinstance(other, Token) and self.kind == other.kind and self.value == other.value


class LexError(Exception):
    pass


def tokenize(text):
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c == "'":
            j = i + 1
            buf = []
            while True:
                if j >= n:
                    raise LexError("unterminated string literal")
                if text[j] == "'":
                    j += 1
                    break
                buf.append(text[j])
                j += 1
            tokens.append(Token("STRING", "".join(buf)))
            i = j
            continue
        if c.isdigit():
            j = i
            is_float = False
            while j < n and (text[j].isdigit() or text[j] == "."):
                if text[j] == ".":
                    is_float = True
                j += 1
            value = text[i:j]
            tokens.append(Token("NUMBER", float(value) if is_float else int(value)))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            word = text[i:j]
            upper = word.upper()
            if upper in KEYWORDS:
                tokens.append(Token("KEYWORD", upper))
            else:
                tokens.append(Token("IDENT", word))
            i = j
            continue
        matched = False
        for sym in SYMBOLS:
            if text.startswith(sym, i):
                tokens.append(Token("SYM", sym))
                i += len(sym)
                matched = True
                break
        if matched:
            continue
        raise LexError(f"unexpected character {c!r} at position {i}")
    tokens.append(Token("EOF", None))
    return tokens
