"""Parser and executor for graphlite's query language.

Supports single-hop directed patterns:

    MATCH (a:Person)-[:KNOWS]->(b:Person)
    WHERE a.age > 30 AND b.city = 'Springfield'
    RETURN a.name, b
    LIMIT 10

Both the label on a node (`:Person`) and the type on an edge (`:KNOWS`)
are optional — an unlabeled node/untyped edge matches anything. WHERE
and LIMIT are optional; RETURN is required. A RETURN item naming a bare
variable (e.g. `b`) returns that node's id/labels/props as a whole;
`a.name` returns just that property.
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
    def __init__(self, left, right, edge_type, where, returns, limit):
        self.left = left
        self.right = right
        self.edge_type = edge_type
        self.where = where
        self.returns = returns
        self.limit = limit


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
        left = self.parse_node_pattern()
        self.expect_sym("-")
        self.expect_sym("[")
        edge_type = None
        if self.at_sym(":"):
            self.advance()
            edge_type = self.parse_ident()
        self.expect_sym("]")
        self.expect_sym("->")
        right = self.parse_node_pattern()

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
        return MatchQuery(left, right, edge_type, where, returns, limit)

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


def execute(graph, query):
    """Run a parsed MatchQuery against a Graph, returning a list of row dicts."""
    left, right = query.left, query.right
    rows = []
    for node_id, node in graph.nodes.items():
        if left.label is not None and left.label not in node["labels"]:
            continue
        for edge_id, edge in graph.out_edges(node_id, edge_type=query.edge_type):
            other_id = edge["to"]
            other_node = graph.nodes[other_id]
            if right.label is not None and right.label not in other_node["labels"]:
                continue
            binding = {left.var: node_id, right.var: other_id}
            if not _matches_where(graph, binding, query.where):
                continue
            rows.append(_build_row(graph, binding, query.returns))
            if query.limit is not None and len(rows) >= query.limit:
                return rows
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
