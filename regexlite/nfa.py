"""Thompson's construction: compile a regex AST into an NFA of States
linked by epsilon/consuming transitions, simulated by matcher.py."""

from .ast_nodes import Alt, Any, Char, CharClass, Concat, End, Plus, Quest, Star, Start


class State:
    """One NFA node. `kind` determines how it's interpreted:

    - 'char'/'class'/'any': consumes one input character via `test(ch)`,
      then control flows to `out`.
    - 'start'/'end': zero-width assertion checked against the current
      position via `test(pos, length)`; passes through to `out` with no
      input consumed.
    - 'split': epsilon-branches to both `out` and `out2` (used for
      alternation and repetition).
    - 'match': accepting state, no outgoing edges.
    """

    __slots__ = ("kind", "test", "out", "out2")

    def __init__(self, kind, test=None, out=None, out2=None):
        self.kind = kind
        self.test = test
        self.out = out
        self.out2 = out2


class Frag:
    """A partially-built NFA fragment: an entry state plus a list of
    dangling (state, attr) outputs still needing to be patched to
    whatever comes next."""

    __slots__ = ("start", "dangling")

    def __init__(self, start, dangling):
        self.start = start
        self.dangling = dangling


def _patch(dangling, target):
    for state, attr in dangling:
        setattr(state, attr, target)


def _compile_node(node):
    if isinstance(node, Char):
        ch = node.ch
        s = State("char", test=(lambda c, ch=ch: c == ch))
        return Frag(s, [(s, "out")])
    if isinstance(node, Any):
        s = State("any", test=lambda c: True)
        return Frag(s, [(s, "out")])
    if isinstance(node, CharClass):
        s = State("class", test=node.matches)
        return Frag(s, [(s, "out")])
    if isinstance(node, Start):
        s = State("start", test=lambda pos, length: pos == 0)
        return Frag(s, [(s, "out")])
    if isinstance(node, End):
        s = State("end", test=lambda pos, length: pos == length)
        return Frag(s, [(s, "out")])
    if isinstance(node, Concat):
        parts = node.parts
        if not parts:
            s = State("split")
            return Frag(s, [(s, "out")])
        frag = _compile_node(parts[0])
        for part in parts[1:]:
            nxt = _compile_node(part)
            _patch(frag.dangling, nxt.start)
            frag = Frag(frag.start, nxt.dangling)
        return frag
    if isinstance(node, Alt):
        branches = [_compile_node(b) for b in node.branches]
        split_states = []
        for b in branches[:-1]:
            split_states.append(State("split", out=b.start))
        for i in range(len(split_states) - 1):
            split_states[i].out2 = split_states[i + 1].start
        if split_states:
            split_states[-1].out2 = branches[-1].start
            start = split_states[0]
        else:
            start = branches[0].start
        dangling = []
        for b in branches:
            dangling.extend(b.dangling)
        return Frag(start, dangling)
    if isinstance(node, Star):
        inner = _compile_node(node.node)
        split = State("split", out=inner.start)
        _patch(inner.dangling, split)
        return Frag(split, [(split, "out2")])
    if isinstance(node, Plus):
        inner = _compile_node(node.node)
        split = State("split", out=inner.start)
        _patch(inner.dangling, split)
        return Frag(inner.start, [(split, "out2")])
    if isinstance(node, Quest):
        inner = _compile_node(node.node)
        split = State("split", out=inner.start)
        dangling = list(inner.dangling) + [(split, "out2")]
        return Frag(split, dangling)
    raise TypeError(f"unknown AST node: {node!r}")


def compile_nfa(ast):
    frag = _compile_node(ast)
    match_state = State("match")
    _patch(frag.dangling, match_state)
    return frag.start
