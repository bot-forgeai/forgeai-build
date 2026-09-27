"""Parser and executor for graphlite's query language.

Supports directed patterns, chained across any number of hops:

    MATCH (a:Person)-[:KNOWS]->(b:Person)-[:WORKS_AT]->(c:Company)
    WHERE a.age > 30 AND b.city = 'Springfield'
    RETURN a.name, b
    LIMIT 10

Both the label on a node (`:Person`) and the type on an edge (`:KNOWS`)
are optional — an unlabeled node/untyped edge matches anything. WHERE
and LIMIT are optional; RETURN is required. A RETURN item naming a bare
variable (e.g. `b`) returns that node's id/labels/props as a whole;
`a.name` returns just that property. Reusing the same variable name at
two positions in the chain (e.g. `(a)-[:X]->(b)-[:Y]->(a)`) constrains
both positions to the same matched node.
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


class MatchQuery:
    def __init__(self, nodes, edge_types, where, returns, limit):
        self.nodes = nodes
        self.edge_types = edge_types
        self.where = where
        self.returns = returns
        self.limit = limit

    @property
    def left(self):
        return self.nodes[0]

    @property
    def right(self):
        return self.nodes[1]

    @property
    def edge_type(self):
        return self.edge_types[0]


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
        edge_types = []
        while self.at_sym("-"):
            self.advance()
            self.expect_sym("[")
            edge_type = None
            if self.at_sym(":"):
                self.advance()
                edge_type = self.parse_ident()
            self.expect_sym("]")
            self.expect_sym("->")
            edge_types.append(edge_type)
            nodes.append(self.parse_node_pattern())

        where = []
        if self.at_keyword("WHERE"):
            self.advance()
            where.append(self.parse_condition())
            while self.at_keyword("AND"):
                self.advance()
                where.append(self.parse_condition())

        self.expect_keyword("RETURN")
        returns = [self.parse_return_item()]
        while self.at_sym(","):
            self.advance()
            returns.append(self.parse_return_item())

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
        return MatchQuery(nodes, edge_types, where, returns, limit)

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


def execute(graph, query):
    """Run a parsed MatchQuery against a Graph, returning a list of row dicts.

    Walks the chain of node/edge patterns hop by hop, backtracking over
    every matching edge at each step. Reusing a variable name at more
    than one position in the chain constrains those positions to the
    same node, rather than being bound independently.
    """
    nodes, edge_types = query.nodes, query.edge_types
    last_hop = len(nodes) - 1
    rows = []

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
            if not _matches_where(graph, next_binding, query.where):
                return
            rows.append(_build_row(graph, next_binding, query.returns))
            if query.limit is not None and len(rows) >= query.limit:
                raise _LimitReached()
            return

        for edge_id, edge in graph.out_edges(node_id, edge_type=edge_types[hop]):
            recurse(hop + 1, edge["to"], next_binding)

    try:
        for node_id in graph.nodes:
            recurse(0, node_id, {})
    except _LimitReached:
        pass
    return rows


def _matches_where(graph, binding, conditions):
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
