"""Parser and executor for graphlite's query language.

Supports directed patterns, chained across any number of hops:

    MATCH (a:Person)-[:KNOWS]->(b:Person)-[:WORKS_AT]->(c:Company)
    WHERE a.age > 30 AND b.city = 'Springfield'
    RETURN a.name, b
    ORDER BY a.name DESC
    LIMIT 10

Both the label on a node (`:Person`) and the type on an edge (`:KNOWS`)
are optional — an unlabeled node/untyped edge matches anything. WHERE,
ORDER BY, and LIMIT are optional; RETURN is required. A RETURN item
naming a bare variable (e.g. `b`) returns that node's id/labels/props
as a whole; `a.name` returns just that property. Reusing the same
variable name at two positions in the chain (e.g.
`(a)-[:X]->(b)-[:Y]->(a)`) constrains both positions to the same
matched node.

An edge can also be variable-length: `[:KNOWS*2]` (exactly 2 hops),
`[:KNOWS*1..3]` (1 to 3 hops inclusive), `[:KNOWS*2..]` (2 or more),
or `[:KNOWS*..3]` (1 to 3). Every edge along a variable-length hop
must share the same type (or be untyped, e.g. `[*1..3]`, to match
any). Only simple paths (no repeated node) are considered, so a cycle
in the graph can't produce an infinite match; a distinct path of a
given length produces its own row, so two different paths reaching
the same end node both appear in the results.

ORDER BY takes one or more `var.prop [ASC|DESC]` items (default ASC),
comma-separated for a multi-key sort; a row missing the property
always sorts last regardless of direction. When present, the whole
result set is gathered and sorted before LIMIT is applied, rather than
LIMIT cutting the match short as it does with no ORDER BY.

WHERE supports both AND and OR, with the usual precedence (AND binds
tighter than OR, so `a.x = 1 AND a.y = 2 OR a.z = 3` reads as
`(a.x = 1 AND a.y = 2) OR (a.z = 3)`). Parentheses inside WHERE are not
supported for further grouping.
"""

from .lexer import tokenize
from .model import GraphError

COMPARISON_OPS = {"=", "!=", "<", "<=", ">", ">="}


class QueryError(Exception):
    pass


class NodePattern:
    def __init__(self, var, label=None):
        self.var = var
        self.label = label


class EdgeSpec:
    """One hop in a MATCH chain: an edge type plus a hop-count range.

    A plain `[:TYPE]` (or untyped `[]`) hop has min_hops == max_hops == 1.
    A variable-length hop (`[:TYPE*min..max]`) has max_hops of None for an
    unbounded upper end (still capped in practice by simple-path length).
    """

    def __init__(self, edge_type, min_hops=1, max_hops=1):
        self.edge_type = edge_type
        self.min_hops = min_hops
        self.max_hops = max_hops

    @property
    def is_variable(self):
        return self.min_hops != 1 or self.max_hops != 1


class Condition:
    def __init__(self, var, prop, op, value):
        self.var = var
        self.prop = prop
        self.op = op
        self.value = value


class ReturnItem:
    def __init__(self, var, prop=None):
        self.var = var
        self.prop = prop


class OrderItem:
    def __init__(self, var, prop, descending=False):
        self.var = var
        self.prop = prop
        self.descending = descending


class MatchQuery:
    def __init__(self, nodes, edge_specs, where_groups, returns, order_by, limit):
        self.nodes = nodes
        self.edge_specs = edge_specs
        self.where_groups = where_groups
        self.returns = returns
        self.order_by = order_by
        self.limit = limit

    @property
    def where(self):
        """The flat AND-list of conditions, for queries with no OR.

        Kept for backward compatibility with callers that predate OR
        support, when WHERE was always a single flat AND-list. Raises
        if the query actually uses OR (more than one group), since a
        flat list can't represent that.
        """
        if len(self.where_groups) > 1:
            raise AttributeError("query uses OR; use where_groups instead")
        return self.where_groups[0] if self.where_groups else []

    @property
    def left(self):
        return self.nodes[0]

    @property
    def right(self):
        return self.nodes[1]

    @property
    def edge_types(self):
        """Kept for backward compatibility with callers that predate variable-length hops."""
        return [spec.edge_type for spec in self.edge_specs]

    @property
    def edge_type(self):
        return self.edge_specs[0].edge_type


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect_sym(self, value):
        tok = self.peek()
        if tok.kind != "SYM" or tok.value != value:
            raise QueryError(f"expected {value!r}, got {tok.kind} {tok.value!r}")
        return self.advance()

    def expect_keyword(self, value):
        tok = self.peek()
        if tok.kind != "KEYWORD" or tok.value != value:
            raise QueryError(f"expected {value}, got {tok.kind} {tok.value!r}")
        return self.advance()

    def at_keyword(self, value):
        tok = self.peek()
        return tok.kind == "KEYWORD" and tok.value == value

    def at_sym(self, value):
        tok = self.peek()
        return tok.kind == "SYM" and tok.value == value

    def parse_ident(self):
        tok = self.peek()
        if tok.kind != "IDENT":
            raise QueryError(f"expected identifier, got {tok.kind} {tok.value!r}")
        return self.advance().value

    def parse_node_pattern(self):
        self.expect_sym("(")
        var = self.parse_ident()
        label = None
        if self.at_sym(":"):
            self.advance()
            label = self.parse_ident()
        self.expect_sym(")")
        return NodePattern(var, label)

    def parse_match_query(self):
        self.expect_keyword("MATCH")
        nodes = [self.parse_node_pattern()]
        edge_specs = []
        while self.at_sym("-"):
            self.advance()
            self.expect_sym("[")
            edge_type = None
            if self.at_sym(":"):
                self.advance()
                edge_type = self.parse_ident()
            min_hops, max_hops = 1, 1
            if self.at_sym("*"):
                self.advance()
                min_hops, max_hops = self.parse_hop_range()
            self.expect_sym("]")
            self.expect_sym("->")
            edge_specs.append(EdgeSpec(edge_type, min_hops, max_hops))
            nodes.append(self.parse_node_pattern())

        where_groups = []
        if self.at_keyword("WHERE"):
            self.advance()
            where_groups = self.parse_where_groups()

        self.expect_keyword("RETURN")
        returns = [self.parse_return_item()]
        while self.at_sym(","):
            self.advance()
            returns.append(self.parse_return_item())

        order_by = []
        if self.at_keyword("ORDER"):
            self.advance()
            self.expect_keyword("BY")
            order_by.append(self.parse_order_item())
            while self.at_sym(","):
                self.advance()
                order_by.append(self.parse_order_item())

        limit = None
        if self.at_keyword("LIMIT"):
            self.advance()
            tok = self.peek()
            if tok.kind != "NUMBER":
                raise QueryError(f"expected a number after LIMIT, got {tok.kind} {tok.value!r}")
            limit = self.advance().value

        if self.peek().kind != "EOF":
            tok = self.peek()
            raise QueryError(f"unexpected trailing {tok.kind} {tok.value!r}")
        return MatchQuery(nodes, edge_specs, where_groups, returns, order_by, limit)

    def parse_hop_range(self):
        """Parse what follows '*' in a variable-length edge: N, N.., ..N, or N..M."""
        if self.at_sym("."):
            self.advance()
            self.expect_sym(".")
            if self.peek().kind != "NUMBER":
                raise QueryError(f"expected a number after '*..', got {self.peek().kind} {self.peek().value!r}")
            max_hops = self._expect_hop_count()
            return 1, max_hops

        min_hops = self._expect_hop_count()
        if not self.at_sym("."):
            return min_hops, min_hops
        self.advance()
        self.expect_sym(".")
        if self.peek().kind != "NUMBER":
            return min_hops, None
        max_hops = self._expect_hop_count()
        return min_hops, max_hops

    def _expect_hop_count(self):
        tok = self.peek()
        if tok.kind != "NUMBER" or not isinstance(tok.value, int):
            raise QueryError(f"expected an integer hop count, got {tok.kind} {tok.value!r}")
        return self.advance().value

    def parse_order_item(self):
        var = self.parse_ident()
        self.expect_sym(".")
        prop = self.parse_ident()
        descending = False
        if self.at_keyword("ASC"):
            self.advance()
        elif self.at_keyword("DESC"):
            self.advance()
            descending = True
        return OrderItem(var, prop, descending)

    def parse_where_groups(self):
        """Parse an OR-of-AND-groups condition list (AND binds tighter than OR)."""
        groups = [self.parse_and_group()]
        while self.at_keyword("OR"):
            self.advance()
            groups.append(self.parse_and_group())
        return groups

    def parse_and_group(self):
        conditions = [self.parse_condition()]
        while self.at_keyword("AND"):
            self.advance()
            conditions.append(self.parse_condition())
        return conditions

    def parse_condition(self):
        var = self.parse_ident()
        self.expect_sym(".")
        prop = self.parse_ident()
        tok = self.peek()
        if tok.kind != "SYM" or tok.value not in COMPARISON_OPS:
            raise QueryError(f"expected a comparison operator, got {tok.kind} {tok.value!r}")
        op = self.advance().value
        value = self.parse_value()
        return Condition(var, prop, op, value)

    def parse_value(self):
        tok = self.peek()
        if tok.kind in ("NUMBER", "STRING"):
            return self.advance().value
        if tok.kind == "KEYWORD" and tok.value == "TRUE":
            self.advance()
            return True
        if tok.kind == "KEYWORD" and tok.value == "FALSE":
            self.advance()
            return False
        raise QueryError(f"expected a value, got {tok.kind} {tok.value!r}")

    def parse_return_item(self):
        var = self.parse_ident()
        prop = None
        if self.at_sym("."):
            self.advance()
            prop = self.parse_ident()
        return ReturnItem(var, prop)


def parse(text):
    tokens = tokenize(text)
    return Parser(tokens).parse_match_query()


def _compare(op, actual, expected):
    if actual is None:
        return False
    try:
        if op == "=":
            return actual == expected
        if op == "!=":
            return actual != expected
        if op == "<":
            return actual < expected
        if op == "<=":
            return actual <= expected
        if op == ">":
            return actual > expected
        if op == ">=":
            return actual >= expected
    except TypeError:
        return False
    raise QueryError(f"unknown operator {op!r}")


def _node_view(graph, node_id):
    node = graph.nodes[node_id]
    return {"id": node_id, "labels": list(node["labels"]), "props": dict(node["props"])}


class _LimitReached(Exception):
    pass


def _variable_length_targets(graph, start, edge_type, min_hops, max_hops):
    """Yield each node reachable from start via a simple path of edge_type edges.

    Only simple paths (no repeated node) are explored, so a cycle can't
    produce an infinite walk. A node reachable by more than one qualifying
    path length is yielded once per such path, not deduplicated — each
    distinct path is its own match, mirroring how a fixed-length chain
    produces one row per matching edge.
    """
    visited = {start}

    def dfs(node_id, depth):
        if max_hops is not None and depth >= max_hops:
            return
        for edge_id, edge in graph.out_edges(node_id, edge_type=edge_type):
            target = edge["to"]
            if target in visited:
                continue
            next_depth = depth + 1
            visited.add(target)
            if next_depth >= min_hops:
                yield target
            yield from dfs(target, next_depth)
            visited.discard(target)

    yield from dfs(start, 0)


def execute(graph, query):
    """Run a parsed MatchQuery against a Graph, returning a list of row dicts.

    Walks the chain of node/edge patterns hop by hop, backtracking over
    every matching edge at each step. Reusing a variable name at more
    than one position in the chain constrains those positions to the
    same node, rather than being bound independently.
    """
    nodes, edge_specs = query.nodes, query.edge_specs
    last_hop = len(nodes) - 1
    bindings = []
    # A sort happens after every match is collected, so LIMIT can't cut the
    # traversal short until the full result set has been ordered.
    can_stop_early = not query.order_by

    def recurse(hop, node_id, binding):
        pattern = nodes[hop]
        if pattern.var in binding:
            if binding[pattern.var] != node_id:
                return
            next_binding = binding
        else:
            node = graph.nodes[node_id]
            if pattern.label is not None and pattern.label not in node["labels"]:
                return
            next_binding = dict(binding)
            next_binding[pattern.var] = node_id

        if hop == last_hop:
            if not _matches_where(graph, next_binding, query.where_groups):
                return
            bindings.append(next_binding)
            if can_stop_early and query.limit is not None and len(bindings) >= query.limit:
                raise _LimitReached()
            return

        spec = edge_specs[hop]
        if spec.is_variable:
            for target in _variable_length_targets(graph, node_id, spec.edge_type, spec.min_hops, spec.max_hops):
                recurse(hop + 1, target, next_binding)
        else:
            for edge_id, edge in graph.out_edges(node_id, edge_type=spec.edge_type):
                recurse(hop + 1, edge["to"], next_binding)

    try:
        for node_id in graph.nodes:
            recurse(0, node_id, {})
    except _LimitReached:
        pass

    if query.order_by:
        bindings = _sort_bindings(graph, bindings, query.order_by)
        if query.limit is not None:
            bindings = bindings[: query.limit]

    return [_build_row(graph, binding, query.returns) for binding in bindings]


class _SortKey:
    """Wraps a row's sort values so None always sorts last regardless of direction."""

    def __init__(self, values):
        self.values = values

    def __lt__(self, other):
        for (v1, desc), (v2, _) in zip(self.values, other.values):
            if v1 is None and v2 is None:
                continue
            if v1 is None:
                return False
            if v2 is None:
                return True
            if v1 == v2:
                continue
            return (v1 < v2) != desc
        return False


def _sort_bindings(graph, bindings, order_by):
    def key(binding):
        values = []
        for item in order_by:
            if item.var not in binding:
                raise QueryError(f"unbound variable {item.var!r} in ORDER BY")
            node_id = binding[item.var]
            value = graph.nodes[node_id]["props"].get(item.prop)
            values.append((value, item.descending))
        return _SortKey(values)

    return sorted(bindings, key=key)


def _matches_where(graph, binding, where_groups):
    """True if binding satisfies (group1 AND ... ) OR (group2 AND ...) OR ...

    An empty group list (no WHERE clause at all) always matches.
    """
    if not where_groups:
        return True
    return any(_matches_and_group(graph, binding, group) for group in where_groups)


def _matches_and_group(graph, binding, conditions):
    for cond in conditions:
        if cond.var not in binding:
            raise QueryError(f"unbound variable {cond.var!r} in WHERE")
        node_id = binding[cond.var]
        actual = graph.nodes[node_id]["props"].get(cond.prop)
        if not _compare(cond.op, actual, cond.value):
            return False
    return True


def _build_row(graph, binding, returns):
    row = {}
    for item in returns:
        if item.var not in binding:
            raise QueryError(f"unbound variable {item.var!r} in RETURN")
        node_id = binding[item.var]
        if item.prop is None:
            key = item.var
            row[key] = _node_view(graph, node_id)
        else:
            key = f"{item.var}.{item.prop}"
            row[key] = graph.nodes[node_id]["props"].get(item.prop)
    return row
