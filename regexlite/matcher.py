"""Pike's algorithm: simulate the Thompson NFA over the input directly,
tracking a set of "live" states per position instead of backtracking.
This makes worst-case matching linear in len(text) * size(pattern),
unlike a naive backtracking engine which can blow up exponentially on
patterns like `(a*)*b` against a long run of `a`s."""

from .nfa import compile_nfa
from .parser import Parser


class Match:
    def __init__(self, string, start, end, caps=()):
        self.string = string
        self.start_pos = start
        self.end_pos = end
        self._caps = caps

    def group(self, n=0):
        if n == 0:
            return self.string[self.start_pos:self.end_pos]
        s, e = self._group_span(n)
        if s is None:
            return None
        return self.string[s:e]

    def groups(self):
        return tuple(self.group(i + 1) for i in range(len(self._caps) // 2))

    def start(self, n=0):
        if n == 0:
            return self.start_pos
        return self._group_span(n)[0]

    def end(self, n=0):
        if n == 0:
            return self.end_pos
        return self._group_span(n)[1]

    def span(self, n=0):
        if n == 0:
            return (self.start_pos, self.end_pos)
        return self._group_span(n)

    def _group_span(self, n):
        i = 2 * (n - 1)
        if i < 0 or i + 1 >= len(self._caps):
            raise IndexError(f"no such group: {n}")
        return (self._caps[i], self._caps[i + 1])

    def __repr__(self):
        return f"Match({self.group()!r}, span={self.span()})"


def _add_state(state, pos, length, out_list, visited, caps):
    if state is None or id(state) in visited:
        return
    visited.add(id(state))
    if state.kind == "split":
        _add_state(state.out, pos, length, out_list, visited, caps)
        _add_state(state.out2, pos, length, out_list, visited, caps)
    elif state.kind in ("start", "end"):
        if state.test(pos, length):
            _add_state(state.out, pos, length, out_list, visited, caps)
    elif state.kind == "save":
        slot = state.slot
        new_caps = caps[:slot] + (pos,) + caps[slot + 1:]
        _add_state(state.out, pos, length, out_list, visited, new_caps)
    else:
        out_list.append((state, caps))


class Pattern:
    def __init__(self, pattern):
        self.pattern = pattern
        parser = Parser(pattern)
        self._ast = parser.parse()
        self.ngroups = parser.group_count
        self._start_state = compile_nfa(self._ast)

    def _run_from(self, text, start_pos):
        """Return (end, caps) for the furthest end position reachable by
        any thread that starts at start_pos, or (None, None) if no
        thread ever reaches 'match'."""
        length = len(text)
        empty_caps = (None,) * (2 * self.ngroups)
        clist = []
        visited = set()
        _add_state(self._start_state, start_pos, length, clist, visited, empty_caps)

        matched_end = None
        matched_caps = None
        for s, caps in clist:
            if s.kind == "match":
                matched_end = start_pos
                matched_caps = caps
                break

        pos = start_pos
        while clist and pos < length:
            ch = text[pos]
            nlist = []
            visited2 = set()
            for s, caps in clist:
                if s.kind in ("char", "class", "any") and s.test(ch):
                    _add_state(s.out, pos + 1, length, nlist, visited2, caps)
            clist = nlist
            pos += 1
            for s, caps in clist:
                if s.kind == "match":
                    matched_end = pos
                    matched_caps = caps
                    break
        return matched_end, matched_caps

    def match(self, text, pos=0):
        end, caps = self._run_from(text, pos)
        if end is None:
            return None
        return Match(text, pos, end, caps)

    def fullmatch(self, text):
        end, caps = self._run_from(text, 0)
        if end != len(text):
            return None
        return Match(text, 0, end, caps)

    def search(self, text):
        for start in range(len(text) + 1):
            end, caps = self._run_from(text, start)
            if end is not None:
                return Match(text, start, end, caps)
        return None

    def findall(self, text):
        results = []
        pos = 0
        while pos <= len(text):
            end, caps = self._run_from(text, pos)
            if end is not None:
                results.append(Match(text, pos, end, caps))
                pos = end + 1 if end == pos else end
            else:
                pos += 1
        return results


def compile(pattern):
    return Pattern(pattern)


def match(pattern, text):
    return Pattern(pattern).match(text)


def fullmatch(pattern, text):
    return Pattern(pattern).fullmatch(text)


def search(pattern, text):
    return Pattern(pattern).search(text)


def findall(pattern, text):
    return [m.group() for m in Pattern(pattern).findall(text)]
