class Char:
    def __init__(self, ch):
        self.ch = ch

    def __repr__(self):
        return f"Char({self.ch!r})"


class Any:
    def __repr__(self):
        return "Any()"


class CharClass:
    def __init__(self, ranges, negate=False):
        # ranges: list of (lo, hi) inclusive character-code pairs
        self.ranges = ranges
        self.negate = negate

    def matches(self, ch):
        code = ord(ch)
        inside = any(lo <= code <= hi for lo, hi in self.ranges)
        return inside != self.negate

    def __repr__(self):
        return f"CharClass({self.ranges!r}, negate={self.negate})"


class Start:
    def __repr__(self):
        return "Start()"


class End:
    def __repr__(self):
        return "End()"


class Concat:
    def __init__(self, parts):
        self.parts = parts

    def __repr__(self):
        return f"Concat({self.parts!r})"


class Alt:
    def __init__(self, branches):
        self.branches = branches

    def __repr__(self):
        return f"Alt({self.branches!r})"


class Star:
    def __init__(self, node):
        self.node = node

    def __repr__(self):
        return f"Star({self.node!r})"


class Plus:
    def __init__(self, node):
        self.node = node

    def __repr__(self):
        return f"Plus({self.node!r})"


class Quest:
    def __init__(self, node):
        self.node = node

    def __repr__(self):
        return f"Quest({self.node!r})"


class Group:
    """A capturing group: `(...)`. `index` is its 1-based capture-group
    number, assigned left-to-right by opening paren, matching the
    convention of Python's own `re` module."""

    def __init__(self, node, index):
        self.node = node
        self.index = index

    def __repr__(self):
        return f"Group({self.node!r}, index={self.index})"
