"""Table storage and statement execution for nanosql."""

from .ast_nodes import BoolOp, Cmp
from .lexer import LexError
from .parser import ParseError, parse

TYPE_CASTS = {
    "INT": int,
    "REAL": float,
    "TEXT": str,
}


class NanosqlError(Exception):
    pass


def _cast(value, col_type):
    if value is None:
        return None
    try:
        return TYPE_CASTS[col_type](value)
    except (TypeError, ValueError):
        raise NanosqlError(f"cannot store {value!r} in a {col_type} column")


class Table:
    def __init__(self, name, columns):
        self.name = name
        self.columns = columns  # list of (name, type)
        self.rows = []

    def column_names(self):
        return [name for name, _ in self.columns]

    def column_type(self, name):
        for col_name, col_type in self.columns:
            if col_name == name:
                return col_type
        raise NanosqlError(f"no such column {name!r} in table {self.name!r}")

    def to_dict(self):
        return {"columns": [[n, t] for n, t in self.columns], "rows": self.rows}

    @classmethod
    def from_dict(cls, name, data):
        table = cls(name, [(n, t) for n, t in data["columns"]])
        table.rows = data["rows"]
        return table


def _eval_where(expr, row):
    if expr is None:
        return True
    if isinstance(expr, Cmp):
        actual = row.get(expr.column)
        if actual is None or expr.value is None:
            if expr.op == "=":
                return actual == expr.value
            if expr.op == "!=":
                return actual != expr.value
            return False
        if expr.op == "=":
            return actual == expr.value
        if expr.op == "!=":
            return actual != expr.value
        if expr.op == "<":
            return actual < expr.value
        if expr.op == "<=":
            return actual <= expr.value
        if expr.op == ">":
            return actual > expr.value
        if expr.op == ">=":
            return actual >= expr.value
        raise NanosqlError(f"unknown operator {expr.op!r}")
    if isinstance(expr, BoolOp):
        if expr.op == "AND":
            return _eval_where(expr.left, row) and _eval_where(expr.right, row)
        if expr.op == "OR":
            return _eval_where(expr.left, row) or _eval_where(expr.right, row)
    raise NanosqlError(f"unknown WHERE expression {expr!r}")


class Database:
    def __init__(self):
        self.tables = {}

    def _table(self, name):
        if name not in self.tables:
            raise NanosqlError(f"no such table {name!r}")
        return self.tables[name]

    def execute(self, sql):
        try:
            stmt = parse(sql)
        except (LexError, ParseError) as exc:
            raise NanosqlError(f"syntax error: {exc}")
        kind = type(stmt).__name__
        return getattr(self, f"_exec_{kind}")(stmt)

    def _exec_CreateTable(self, stmt):
        if stmt.table in self.tables:
            raise NanosqlError(f"table {stmt.table!r} already exists")
        self.tables[stmt.table] = Table(stmt.table, stmt.columns)
        return {"kind": "ok", "message": f"table {stmt.table!r} created"}

    def _exec_Insert(self, stmt):
        table = self._table(stmt.table)
        columns = stmt.columns if stmt.columns is not None else table.column_names()
        if len(columns) != len(stmt.values):
            raise NanosqlError(
                f"column count {len(columns)} does not match value count {len(stmt.values)}"
            )
        for name in columns:
            table.column_type(name)  # validates the column exists
        row = {name: None for name in table.column_names()}
        for name, value in zip(columns, stmt.values):
            row[name] = _cast(value, table.column_type(name))
        table.rows.append(row)
        return {"kind": "ok", "message": "1 row inserted"}

    def _exec_Select(self, stmt):
        table = self._table(stmt.table)
        columns = table.column_names() if stmt.columns == ["*"] else stmt.columns
        for name in columns:
            table.column_type(name)
        matches = [row for row in table.rows if _eval_where(stmt.where, row)]
        if stmt.order_by is not None:
            col, direction = stmt.order_by
            table.column_type(col)
            matches = sorted(matches, key=lambda r: (r[col] is None, r[col]), reverse=(direction == "DESC"))
        if stmt.limit is not None:
            matches = matches[: stmt.limit]
        rows = [{name: row[name] for name in columns} for row in matches]
        return {"kind": "rows", "columns": columns, "rows": rows}

    def _exec_Update(self, stmt):
        table = self._table(stmt.table)
        for col, _ in stmt.assignments:
            table.column_type(col)
        count = 0
        for row in table.rows:
            if _eval_where(stmt.where, row):
                for col, value in stmt.assignments:
                    row[col] = _cast(value, table.column_type(col))
                count += 1
        return {"kind": "ok", "message": f"{count} row(s) updated"}

    def _exec_Delete(self, stmt):
        table = self._table(stmt.table)
        before = len(table.rows)
        table.rows = [row for row in table.rows if not _eval_where(stmt.where, row)]
        count = before - len(table.rows)
        return {"kind": "ok", "message": f"{count} row(s) deleted"}

    def to_dict(self):
        return {"tables": {name: table.to_dict() for name, table in self.tables.items()}}

    @classmethod
    def from_dict(cls, data):
        db = cls()
        for name, table_data in data.get("tables", {}).items():
            db.tables[name] = Table.from_dict(name, table_data)
        return db
