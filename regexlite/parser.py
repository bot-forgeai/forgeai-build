from .ast_nodes import Alt, Any, Char, CharClass, Concat, End, Plus, Quest, Star, Start

SPECIAL = set(".^$*+?()[]|\\")

SHORTHAND = {
    "d": [(ord("0"), ord("9"))],
    "w": [(ord("a"), ord("z")), (ord("A"), ord("Z")), (ord("0"), ord("9")), (ord("_"), ord("_"))],
    "s": [(ord(" "), ord(" ")), (ord("\t"), ord("\t")), (ord("\n"), ord("\n")),
          (ord("\r"), ord("\r")), (ord("\f"), ord("\f")), (ord("\v"), ord("\v"))],
}


class RegexSyntaxError(Exception):
    pass


class Parser:
    def __init__(self, pattern):
        self.pattern = pattern
        self.pos = 0

    def peek(self):
        if self.pos < len(self.pattern):
            return self.pattern[self.pos]
        return None

    def advance(self):
        ch = self.peek()
        self.pos += 1
        return ch

    def parse(self):
        node = self.parse_alt()
        if self.pos != len(self.pattern):
            raise RegexSyntaxError(f"unexpected character at position {self.pos}: {self.peek()!r}")
        return node

    def parse_alt(self):
        branches = [self.parse_concat()]
        while self.peek() == "|":
            self.advance()
            branches.append(self.parse_concat())
        if len(branches) == 1:
            return branches[0]
        return Alt(branches)

    def parse_concat(self):
        parts = []
        while self.peek() is not None and self.peek() not in ("|", ")"):
            parts.append(self.parse_repeat())
        if len(parts) == 1:
            return parts[0]
        return Concat(parts)

    def parse_repeat(self):
        atom = self.parse_atom()
        while self.peek() in ("*", "+", "?"):
            op = self.advance()
            if op == "*":
                atom = Star(atom)
            elif op == "+":
                atom = Plus(atom)
            else:
                atom = Quest(atom)
        return atom

    def parse_atom(self):
        ch = self.peek()
        if ch is None:
            raise RegexSyntaxError("unexpected end of pattern")
        if ch == "(":
            self.advance()
            node = self.parse_alt()
            if self.peek() != ")":
                raise RegexSyntaxError("unbalanced parenthesis")
            self.advance()
            return node
        if ch == "[":
            return self.parse_charclass()
        if ch == ".":
            self.advance()
            return Any()
        if ch == "^":
            self.advance()
            return Start()
        if ch == "$":
            self.advance()
            return End()
        if ch == "\\":
            self.advance()
            esc = self.advance()
            if esc is None:
                raise RegexSyntaxError("dangling escape at end of pattern")
            if esc in SHORTHAND:
                return CharClass(SHORTHAND[esc])
            if esc.isupper() and esc.lower() in SHORTHAND:
                return CharClass(SHORTHAND[esc.lower()], negate=True)
            return Char(esc)
        if ch in (")", "*", "+", "?", "|"):
            raise RegexSyntaxError(f"unexpected metacharacter {ch!r} at position {self.pos}")
        self.advance()
        return Char(ch)

    def parse_charclass(self):
        self.advance()  # consume '['
        negate = False
        if self.peek() == "^":
            negate = True
            self.advance()
        ranges = []
        first = True
        while self.peek() is not None and (self.peek() != "]" or first):
            first = False
            lo = self._class_char()
            if self.peek() == "-" and self.pos + 1 < len(self.pattern) and self.pattern[self.pos + 1] != "]":
                self.advance()
                hi = self._class_char()
                if ord(hi) < ord(lo):
                    raise RegexSyntaxError(f"bad character range {lo}-{hi}")
                ranges.append((ord(lo), ord(hi)))
            else:
                ranges.append((ord(lo), ord(lo)))
        if self.peek() != "]":
            raise RegexSyntaxError("unterminated character class")
        self.advance()
        if not ranges:
            raise RegexSyntaxError("empty character class")
        return CharClass(ranges, negate=negate)

    def _class_char(self):
        ch = self.advance()
        if ch is None:
            raise RegexSyntaxError("unterminated character class")
        if ch == "\\":
            esc = self.advance()
            if esc is None:
                raise RegexSyntaxError("dangling escape in character class")
            return esc
        return ch


def parse(pattern):
    return Parser(pattern).parse()
