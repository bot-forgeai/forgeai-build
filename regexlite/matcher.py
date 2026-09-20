"""Pike's algorithm: simulate the Thompson NFA over the input directly,
tracking a set of "live" states per position instead of backtracking.
This makes worst-case matching linear in len(text) * size(pattern),
unlike a naive backtracking engine which can blow up exponentially on
patterns like `(a*)*b` against a long run of `a`s."""

from .nfa import compile_nfa
from .parser import parse


class Match:
    def __init__(self, string, start, end):
        self.string = string
        self.start_pos = start
        self.end_pos = end

    def group(self):
        return self.string[self.start_pos:self.end_pos]

    def span(self):
        return (self.start_pos, self.end_pos)

    def __repr__(self):
        return f"Match({self.group()!r}, span={self.span()})"


def _add_state(state, pos, length, out_list, visited):
    if state is None or id(state) in visited:
        return
    visited.add(id(state))
    if state.kind == "split":
        _add_state(state.out, pos, length, out_list, visited)
        _add_state(state.out2, pos, length, out_list, visited)
    elif state.kind in ("start", "end"):
        if state.test(pos, length):
            _add_state(state.out, pos, length, out_list, visited)
    else:
        out_list.append(state)


class Pattern:
    def __init__(self, pattern):
        self.pattern = pattern
        self._ast = parse(pattern)
        self._start_state = compile_nfa(self._ast)

    def _run_from(self, text, start_pos):
        """Return the furthest end position reachable by any thread that
        starts at start_pos, or None if no thread ever reaches 'match'."""
        length = len(text)
        clist = []
        visited = set()
        _add_state(self._start_state, start_pos, length, clist, visited)

        matched_end = None
        if any(s.kind == "match" for s in clist):
            matched_end = start_pos

        pos = start_pos
        while clist and pos < length:
            ch = text[pos]
            nlist = []
            visited2 = set()
            for s in clist:
                if s.kind in ("char", "class", "any") and s.test(ch):
                    _add_state(s.out, pos + 1, length, nlist, visited2)
            clist = nlist
            pos += 1
            if any(s.kind == "match" for s in clist):
                matched_end = pos
        return matched_end

    def match(self, text, pos=0):
        end = self._run_from(text, pos)
        if end is None:
            return None
        return Match(text, pos, end)

    def fullmatch(self, text):
        end = self._run_from(text, 0)
        if end != len(text):
            return None
        return Match(text, 0, end)

    def search(self, text):
        for start in range(len(text) + 1):
            end = self._run_from(text, start)
            if end is not None:
                return Match(text, start, end)
        return None

    def findall(self, text):
        results = []
        pos = 0
        while pos <= len(text):
            end = self._run_from(text, pos)
            if end is not None:
                results.append(Match(text, pos, end))
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
