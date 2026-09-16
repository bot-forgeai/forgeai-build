"""Tokenizer for nanosql's SQL subset."""

KEYWORDS = {
    "CREATE", "TABLE", "INSERT", "INTO", "VALUES", "SELECT", "FROM", "WHERE",
    "AND", "OR", "NOT", "ORDER", "BY", "ASC", "DESC", "LIMIT", "UPDATE",
    "SET", "DELETE", "NULL", "TRUE", "FALSE", "INT", "REAL", "TEXT",
    "COUNT", "SUM", "AVG", "MIN", "MAX", "GROUP", "JOIN", "ON", "INDEX",
}

SYMBOLS = ["<=", ">=", "!=", "<>", "=", "<", ">", ",", "(", ")", ";", "*", "."]


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


def tokenize(sql):
    tokens = []
    i = 0
    n = len(sql)
    while i < n:
        c = sql[i]
        if c.isspace():
            i += 1
            continue
        if c == "'":
            j = i + 1
            buf = []
            while True:
                if j >= n:
                    raise LexError("unterminated string literal")
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        buf.append("'")
                        j += 2
                        continue
                    j += 1
                    break
                buf.append(sql[j])
                j += 1
            tokens.append(Token("STRING", "".join(buf)))
            i = j
            continue
        if c.isdigit() or (c == "." and i + 1 < n and sql[i + 1].isdigit()):
            j = i
            is_float = False
            while j < n and (sql[j].isdigit() or sql[j] == "."):
                if sql[j] == ".":
                    is_float = True
                j += 1
            text = sql[i:j]
            tokens.append(Token("NUMBER", float(text) if is_float else int(text)))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            word = sql[i:j]
            upper = word.upper()
            if upper in KEYWORDS:
                tokens.append(Token("KEYWORD", upper))
            else:
                tokens.append(Token("IDENT", word))
            i = j
            continue
        matched = False
        for sym in SYMBOLS:
            if sql.startswith(sym, i):
                kind = "PUNCT" if sym in (",", "(", ")", ";", "*", ".") else "OP"
                value = "!=" if sym == "<>" else sym
                tokens.append(Token(kind, value))
                i += len(sym)
                matched = True
                break
        if matched:
            continue
        raise LexError(f"unexpected character {c!r} at position {i}")
    tokens.append(Token("EOF", None))
    return tokens
