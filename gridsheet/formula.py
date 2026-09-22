"""Formula tokenizer, recursive-descent parser, and evaluator for gridsheet."""
import re

from gridsheet.refs import expand_range, normalize_ref

TOKEN_RE = re.compile(
    r"""
    (?P<NUMBER>\d+\.\d+|\d+)
  | (?P<CELLREF>[A-Za-z]+\d+)
  | (?P<IDENT>[A-Za-z]+)
  | (?P<COLON>:)
  | (?P<COMMA>,)
  | (?P<PLUS>\+)
  | (?P<MINUS>-)
  | (?P<STAR>\*)
  | (?P<SLASH>/)
  | (?P<LPAREN>\()
  | (?P<RPAREN>\))
  | (?P<WS>\s+)
    """,
    re.VERBOSE,
)


class FormulaError(Exception):
    pass


class SheetEvalError(Exception):
    """Raised during evaluation; caught by Sheet and stored as an error value like '#DIV/0!'."""


def tokenize(text):
    tokens = []
    pos = 0
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m:
            raise FormulaError(f"unexpected character {text[pos]!r} at position {pos}")
        kind = m.lastgroup
        value = m.group()
        pos = m.end()
        if kind == "WS":
            continue
        tokens.append((kind, value))
    tokens.append(("EOF", ""))
    return tokens


# AST nodes: simple tuples/classes
class Num:
    def __init__(self, value):
        self.value = value


class CellRef:
    def __init__(self, ref):
        self.ref = normalize_ref(ref)


class Range:
    def __init__(self, start, end):
        self.start = normalize_ref(start)
        self.end = normalize_ref(end)


class BinOp:
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class UnaryOp:
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand


class FuncCall:
    def __init__(self, name, args):
        self.name = name.upper()
        self.args = args


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

    def expect(self, kind):
        tok = self.advance()
        if tok[0] != kind:
            raise FormulaError(f"expected {kind}, got {tok[0]} ({tok[1]!r})")
        return tok

    def parse(self):
        node = self.parse_expr()
        if self.peek()[0] != "EOF":
            raise FormulaError(f"unexpected trailing token {self.peek()}")
        return node

    def parse_expr(self):
        node = self.parse_term()
        while self.peek()[0] in ("PLUS", "MINUS"):
            op = self.advance()[0]
            right = self.parse_term()
            node = BinOp("+" if op == "PLUS" else "-", node, right)
        return node

    def parse_term(self):
        node = self.parse_unary()
        while self.peek()[0] in ("STAR", "SLASH"):
            op = self.advance()[0]
            right = self.parse_unary()
            node = BinOp("*" if op == "STAR" else "/", node, right)
        return node

    def parse_unary(self):
        if self.peek()[0] == "MINUS":
            self.advance()
            return UnaryOp("-", self.parse_unary())
        return self.parse_primary()

    def parse_primary(self):
        kind, value = self.peek()
        if kind == "NUMBER":
            self.advance()
            return Num(float(value))
        if kind == "CELLREF":
            self.advance()
            if self.peek()[0] == "COLON":
                self.advance()
                end_tok = self.expect("CELLREF")
                return Range(value, end_tok[1])
            return CellRef(value)
        if kind == "IDENT":
            self.advance()
            self.expect("LPAREN")
            args = []
            if self.peek()[0] != "RPAREN":
                args.append(self.parse_arg())
                while self.peek()[0] == "COMMA":
                    self.advance()
                    args.append(self.parse_arg())
            self.expect("RPAREN")
            return FuncCall(value, args)
        if kind == "LPAREN":
            self.advance()
            node = self.parse_expr()
            self.expect("RPAREN")
            return node
        raise FormulaError(f"unexpected token {kind} ({value!r})")

    def parse_arg(self):
        # An argument may be a bare range (A1:A3) or a full expression.
        if self.peek()[0] == "CELLREF":
            save = self.pos
            value = self.advance()[1]
            if self.peek()[0] == "COLON":
                self.advance()
                end_tok = self.expect("CELLREF")
                return Range(value, end_tok[1])
            self.pos = save
        return self.parse_expr()


def parse(text):
    return Parser(tokenize(text)).parse()


def extract_refs(node):
    """Return the set of individual cell refs a parsed formula depends on."""
    refs = set()

    def walk(n):
        if isinstance(n, Num):
            return
        if isinstance(n, CellRef):
            refs.add(n.ref)
        elif isinstance(n, Range):
            refs.update(expand_range(n.start, n.end))
        elif isinstance(n, BinOp):
            walk(n.left)
            walk(n.right)
        elif isinstance(n, UnaryOp):
            walk(n.operand)
        elif isinstance(n, FuncCall):
            for a in n.args:
                walk(a)

    walk(node)
    return refs


FUNCS = {"SUM", "AVG", "MIN", "MAX", "COUNT"}


def _as_number(value, ref_desc=""):
    if isinstance(value, str) and value.startswith("#"):
        raise SheetEvalError(value)
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    raise SheetEvalError("#VALUE!")


def evaluate(node, lookup):
    """lookup(ref) -> current value of another cell (number, string, None, or an error string)."""
    if isinstance(node, Num):
        return node.value
    if isinstance(node, CellRef):
        return lookup(node.ref)
    if isinstance(node, Range):
        raise SheetEvalError("#VALUE!")
    if isinstance(node, UnaryOp):
        v = _as_number(evaluate(node.operand, lookup))
        return -v
    if isinstance(node, BinOp):
        left = _as_number(evaluate(node.left, lookup))
        right = _as_number(evaluate(node.right, lookup))
        if node.op == "+":
            return left + right
        if node.op == "-":
            return left - right
        if node.op == "*":
            return left * right
        if node.op == "/":
            if right == 0:
                raise SheetEvalError("#DIV/0!")
            return left / right
    if isinstance(node, FuncCall):
        if node.name not in FUNCS:
            raise SheetEvalError("#NAME?")
        values = []
        for arg in node.args:
            if isinstance(arg, Range):
                for ref in expand_range(arg.start, arg.end):
                    values.append(lookup(ref))
            else:
                values.append(evaluate(arg, lookup))
        nums = [_as_number(v) for v in values if v is not None]
        if node.name == "SUM":
            return sum(nums)
        if node.name == "AVG":
            if not nums:
                raise SheetEvalError("#DIV/0!")
            return sum(nums) / len(nums)
        if node.name == "MIN":
            if not nums:
                raise SheetEvalError("#VALUE!")
            return min(nums)
        if node.name == "MAX":
            if not nums:
                raise SheetEvalError("#VALUE!")
            return max(nums)
        if node.name == "COUNT":
            return float(len(nums))
    raise SheetEvalError("#VALUE!")
