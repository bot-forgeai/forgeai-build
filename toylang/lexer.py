"""Lexer: turns source text into a flat list of Tokens."""


class ToylangSyntaxError(Exception):
    def __init__(self, message, line):
        super().__init__(f"line {line}: {message}")
        self.message = message
        self.line = line


class Token:
    __slots__ = ("type", "value", "line")

    def __init__(self, type_, value, line):
        self.type = type_
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r}, line={self.line})"

    def __eq__(self, other):
        return (
            isinstance(other, Token)
            and self.type == other.type
            and self.value == other.value
        )


KEYWORDS = {
    "let", "if", "else", "while", "func", "return",
    "true", "false", "nil", "and", "or", "not",
}

# Longest-match-first so e.g. "==" isn't lexed as two "=" tokens.
SYMBOLS = [
    "==", "!=", "<=", ">=",
    "+", "-", "*", "/", "%",
    "=", "<", ">",
    "(", ")", "{", "}", ",", ";",
]


def tokenize(source):
    tokens = []
    i = 0
    line = 1
    n = len(source)
    while i < n:
        c = source[i]

        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        if c == "#":
            while i < n and source[i] != "\n":
                i += 1
            continue

        if c.isdigit() or (c == "." and i + 1 < n and source[i + 1].isdigit()):
            start = i
            seen_dot = False
            while i < n and (source[i].isdigit() or (source[i] == "." and not seen_dot)):
                if source[i] == ".":
                    seen_dot = True
                i += 1
            text = source[start:i]
            value = float(text) if seen_dot else int(text)
            tokens.append(Token("NUMBER", value, line))
            continue

        if c == '"':
            start_line = line
            i += 1
            chars = []
            while i < n and source[i] != '"':
                ch = source[i]
                if ch == "\\" and i + 1 < n:
                    nxt = source[i + 1]
                    escapes = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
                    if nxt in escapes:
                        chars.append(escapes[nxt])
                        i += 2
                        continue
                if ch == "\n":
                    line += 1
                chars.append(ch)
                i += 1
            if i >= n:
                raise ToylangSyntaxError("unterminated string literal", start_line)
            i += 1  # closing quote
            tokens.append(Token("STRING", "".join(chars), start_line))
            continue

        if c.isalpha() or c == "_":
            start = i
            while i < n and (source[i].isalnum() or source[i] == "_"):
                i += 1
            text = source[start:i]
            if text in KEYWORDS:
                tokens.append(Token(text.upper(), text, line))
            else:
                tokens.append(Token("IDENT", text, line))
            continue

        matched = None
        for sym in SYMBOLS:
            if source.startswith(sym, i):
                matched = sym
                break
        if matched:
            tokens.append(Token(matched, matched, line))
            i += len(matched)
            continue

        raise ToylangSyntaxError(f"unexpected character {c!r}", line)

    tokens.append(Token("EOF", None, line))
    return tokens
