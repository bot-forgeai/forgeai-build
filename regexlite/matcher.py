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


def _expand_repl(repl, m):
    """Expand backreferences in a replacement string: \\N or \\g<N> is
    replaced by group N's text (empty string if the group exists but
    didn't participate in the match), \\\\ is a literal backslash."""
    out = []
    i = 0
    length = len(repl)
    while i < length:
        ch = repl[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        if i + 1 >= length:
            raise RegexSubError("bad escape at end of replacement string")
        nxt = repl[i + 1]
        if nxt == "\\":
            out.append("\\")
            i += 2
        elif nxt == "g" and i + 2 < length and repl[i + 2] == "<":
            close = repl.find(">", i + 3)
            if close == -1:
                raise RegexSubError("missing '>' in \\g<...> reference")
            num = repl[i + 3:close]
            if not num.isdigit():
                raise RegexSubError(f"bad group reference: \\g<{num}>")
            out.append(_group_text_or_empty(m, int(num)))
            i = close + 1
        elif nxt.isdigit():
            j = i + 1
            while j < length and repl[j].isdigit() and (j - i) <= 2:
                j += 1
            num = int(repl[i + 1:j])
            out.append(_group_text_or_empty(m, num))
            i = j
        else:
            raise RegexSubError(f"bad escape \\{nxt} in replacement string")
    return "".join(out)


class RegexSubError(ValueError):
    pass


def _group_text_or_empty(m, num):
    try:
        return m.group(num) or ""
    except IndexError:
        raise RegexSubError(f"invalid group reference {num}")


class Pattern:
    def __init__(self, pattern):
        self.pattern = pattern
        parser = Parser(pattern)
        self._ast = parser.parse()
        self.ngroups = parser.group_count
        self._start_state = compile_nfa(self._ast)

    def _run_from(self, text, start_pos):
        """Return (end, caps) for the match found by the highest-priority
        thread that reaches 'match', or (None, None) if no thread ever
        does. Threads are kept in priority order (earlier means tried
        first, e.g. a greedy loop body before its exit, or a lazy exit
        before its loop body); when a thread reaches 'match' every
        lower-priority thread still in the list is dropped, since none
        of them can ever produce a result preferred over it."""
        length = len(text)
        empty_caps = (None,) * (2 * self.ngroups)
        clist = []
        visited = set()
        _add_state(self._start_state, start_pos, length, clist, visited, empty_caps)

        matched_end = None
        matched_caps = None
        pos = start_pos
        while True:
            for i, (s, caps) in enumerate(clist):
                if s.kind == "match":
                    matched_end = pos
                    matched_caps = caps
                    clist = clist[:i]
                    break
            if not clist or pos >= length:
                break
            ch = text[pos]
            nlist = []
            visited2 = set()
            for s, caps in clist:
                if s.kind in ("char", "class", "any") and s.test(ch):
                    _add_state(s.out, pos + 1, length, nlist, visited2, caps)
            clist = nlist
            pos += 1
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

    def subn(self, repl, text, count=0):
        expand = repl if callable(repl) else lambda m: _expand_repl(repl, m)
        pieces = []
        pos = 0
        last_end = 0
        n = 0
        while pos <= len(text) and (count <= 0 or n < count):
            end, caps = self._run_from(text, pos)
            if end is not None:
                m = Match(text, pos, end, caps)
                pieces.append(text[last_end:pos])
                pieces.append(expand(m))
                last_end = end
                n += 1
                pos = end + 1 if end == pos else end
            else:
                pos += 1
        pieces.append(text[last_end:])
        return "".join(pieces), n

    def sub(self, repl, text, count=0):
        return self.subn(repl, text, count)[0]


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


def sub(pattern, repl, text, count=0):
    return Pattern(pattern).sub(repl, text, count)


def subn(pattern, repl, text, count=0):
    return Pattern(pattern).subn(repl, text, count)
