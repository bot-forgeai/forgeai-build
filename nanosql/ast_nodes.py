"""AST node types produced by nanosql's parser."""


class CreateTable:
    def __init__(self, table, columns):
        self.table = table
        self.columns = columns  # list of (name, type)


class Insert:
    def __init__(self, table, columns, values):
        self.table = table
        self.columns = columns  # list of names, or None for "all columns in order"
        self.values = values  # list of literal values


class Select:
    def __init__(self, table, columns, where, order_by, limit):
        self.table = table
        self.columns = columns  # list of names, or ["*"]
        self.where = where  # Expr or None
        self.order_by = order_by  # (col, "ASC"|"DESC") or None
        self.limit = limit  # int or None


class Update:
    def __init__(self, table, assignments, where):
        self.table = table
        self.assignments = assignments  # list of (col, value)
        self.where = where


class Delete:
    def __init__(self, table, where):
        self.table = table
        self.where = where


class Cmp:
    """A single WHERE comparison: <column> <op> <literal>."""

    def __init__(self, column, op, value):
        self.column = column
        self.op = op
        self.value = value


class BoolOp:
    """A WHERE 'AND'/'OR' combination of two sub-expressions."""

    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right
