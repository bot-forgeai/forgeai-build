"""AST node types. Plain dataclass-free classes for simplicity."""


class Node:
    pass


# --- Expressions ---

class NumberLit(Node):
    def __init__(self, value):
        self.value = value


class StringLit(Node):
    def __init__(self, value):
        self.value = value


class BoolLit(Node):
    def __init__(self, value):
        self.value = value


class NilLit(Node):
    pass


class Var(Node):
    def __init__(self, name):
        self.name = name


class Assign(Node):
    def __init__(self, name, value):
        self.name = name
        self.value = value


class BinOp(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class UnaryOp(Node):
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand


class Call(Node):
    def __init__(self, callee, args):
        self.callee = callee
        self.args = args


class FuncExpr(Node):
    def __init__(self, params, body):
        self.params = params
        self.body = body


# --- Statements ---

class LetStmt(Node):
    def __init__(self, name, value):
        self.name = name
        self.value = value


class ExprStmt(Node):
    def __init__(self, expr):
        self.expr = expr


class IfStmt(Node):
    def __init__(self, condition, then_block, else_block):
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block


class WhileStmt(Node):
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body


class ReturnStmt(Node):
    def __init__(self, value):
        self.value = value


class FuncDecl(Node):
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body


class Block(Node):
    def __init__(self, statements):
        self.statements = statements


class Program(Node):
    def __init__(self, statements):
        self.statements = statements
