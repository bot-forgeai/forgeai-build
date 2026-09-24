from .ast_nodes import Alt, Any, Char, CharClass, Concat, End, Group, Plus, Quest, Star, Start

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
        self.group_count = 0
        self.group_names = {}

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
        while self.peek() in ("*", "+", "?", "{"):
            if self.peek() == "{":
                bound = self._try_parse_bound()
                if bound is None:
                    break
                lo, hi = bound
                lazy = False
                if self.peek() == "?":
                    self.advance()
                    lazy = True
                atom = self._expand_bound(atom, lo, hi, lazy=lazy)
                continue
            op = self.advance()
            lazy = False
            if self.peek() == "?":
                self.advance()
                lazy = True
            if op == "*":
                atom = Star(atom, lazy=lazy)
            elif op == "+":
                atom = Plus(atom, lazy=lazy)
            else:
                atom = Quest(atom, lazy=lazy)
        return atom

    def _try_parse_bound(self):
        """Try to parse a {m}/{m,}/{m,n} bound starting at the current
        '{'. Returns (lo, hi) with hi=None meaning unbounded, or None if
        what follows isn't a valid bound (so '{' is left to be matched
        as a literal character instead)."""
        text = self.pattern
        n = len(text)
        p = self.pos + 1
        lo_start = p
        while p < n and text[p].isdigit():
            p += 1
        lo_str = text[lo_start:p]
        if lo_str == "":
            return None
        hi_str = lo_str
        if p < n and text[p] == ",":
            p += 1
            hi_start = p
            while p < n and text[p].isdigit():
                p += 1
            hi_str = text[hi_start:p]
        if p >= n or text[p] != "}":
            return None
        p += 1
        lo = int(lo_str)
        hi = None if hi_str == "" else int(hi_str)
        if lo > 1000 or (hi is not None and hi > 1000):
            raise RegexSyntaxError("repetition count too large")
        if hi is not None and hi < lo:
            raise RegexSyntaxError(f"invalid repetition bound {{{lo_str},{hi_str}}}: max < min")
        self.pos = p
        return (lo, hi)

    def _expand_bound(self, atom, lo, hi, lazy=False):
        if hi == 0:
            return Concat([])
        parts = [atom] * lo
        if hi is None:
            parts.append(Star(atom, lazy=lazy))
        else:
            parts.extend([Quest(atom, lazy=lazy) for _ in range(hi - lo)])
        if not parts:
            return Concat([])
        if len(parts) == 1:
            return parts[0]
        return Concat(parts)

    def parse_atom(self):
        ch = self.peek()
        if ch is None:
            raise RegexSyntaxError("unexpected end of pattern")
        if ch == "(":
            self.advance()
            capturing = True
            name = None
            if self.peek() == "?":
                self.advance()
                if self.peek() == ":":
                    self.advance()
                    capturing = False
                elif self.peek() == "P":
                    self.advance()
                    if self.peek() != "<":
                        raise RegexSyntaxError("expected '<' after '(?P'")
                    self.advance()
                    name_start = self.pos
                    while self.peek() is not None and self.peek() != ">":
                        self.advance()
                    if self.peek() != ">":
                        raise RegexSyntaxError("unterminated group name")
                    name = self.pattern[name_start:self.pos]
                    self.advance()  # consume '>'
                    if not name:
                        raise RegexSyntaxError("empty group name")
                    if name in self.group_names:
                        raise RegexSyntaxError(f"duplicate group name {name!r}")
                else:
                    raise RegexSyntaxError(f"unsupported group syntax '(?{self.peek()}'")
            index = None
            if capturing:
                self.group_count += 1
                index = self.group_count
                if name is not None:
                    self.group_names[name] = index
            node = self.parse_alt()
            if self.peek() != ")":
                raise RegexSyntaxError("unbalanced parenthesis")
            self.advance()
            if not capturing:
                return node
            return Group(node, index, name=name)
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
