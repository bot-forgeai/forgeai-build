"""Table storage and statement execution for nanosql."""

from .ast_nodes import AggCall, BoolOp, Cmp
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
        self.indexed_columns = set()
        self.indexes = {}  # column name -> {value: [row dict, ...]}

    def column_names(self):
        return [name for name, _ in self.columns]

    def column_type(self, name):
        for col_name, col_type in self.columns:
            if col_name == name:
                return col_type
        raise NanosqlError(f"no such column {name!r} in table {self.name!r}")

    def create_index(self, column):
        self.column_type(column)  # validates the column exists
        self.indexed_columns.add(column)
        self.rebuild_index(column)

    def rebuild_index(self, column):
        index = {}
        for row in self.rows:
            index.setdefault(row[column], []).append(row)
        self.indexes[column] = index

    def rebuild_all_indexes(self):
        for column in self.indexed_columns:
            self.rebuild_index(column)

    def index_insert(self, row):
        for column in self.indexed_columns:
            self.indexes[column].setdefault(row[column], []).append(row)

    def to_dict(self):
        return {
            "columns": [[n, t] for n, t in self.columns],
            "rows": self.rows,
            "indexed_columns": sorted(self.indexed_columns),
        }

    @classmethod
    def from_dict(cls, name, data):
        table = cls(name, [(n, t) for n, t in data["columns"]])
        table.rows = data["rows"]
        for column in data.get("indexed_columns", []):
            table.create_index(column)
        return table


def _compare(op, actual, value):
    if actual is None or value is None:
        if op == "=":
            return actual == value
        if op == "!=":
            return actual != value
        return False
    if op == "=":
        return actual == value
    if op == "!=":
        return actual != value
    if op == "<":
        return actual < value
    if op == "<=":
        return actual <= value
    if op == ">":
        return actual > value
    if op == ">=":
        return actual >= value
    raise NanosqlError(f"unknown operator {op!r}")


def _eval_where(expr, row):
    if expr is None:
        return True
    if isinstance(expr, Cmp):
        return _compare(expr.op, row.get(expr.column), expr.value)
    if isinstance(expr, BoolOp):
        if expr.op == "AND":
            return _eval_where(expr.left, row) and _eval_where(expr.right, row)
        if expr.op == "OR":
            return _eval_where(expr.left, row) or _eval_where(expr.right, row)
    raise NanosqlError(f"unknown WHERE expression {expr!r}")


def _compute_aggregate(agg, rows):
    if agg.func == "COUNT":
        if agg.column == "*":
            return len(rows)
        return sum(1 for row in rows if row[agg.column] is not None)
    values = [row[agg.column] for row in rows if row[agg.column] is not None]
    if agg.func == "SUM":
        return sum(values) if values else 0
    if agg.func == "AVG":
        return sum(values) / len(values) if values else None
    if agg.func == "MIN":
        return min(values) if values else None
    if agg.func == "MAX":
        return max(values) if values else None
    raise NanosqlError(f"unknown aggregate function {agg.func!r}")


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

    def _exec_CreateIndex(self, stmt):
        table = self._table(stmt.table)
        table.create_index(stmt.column)
        return {"kind": "ok", "message": f"index {stmt.index_name!r} created on {stmt.table}.{stmt.column}"}

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
        table.index_insert(row)
        return {"kind": "ok", "message": "1 row inserted"}

    def _join_rows(self, left, right, on):
        left_cols = left.column_names()
        right_cols = right.column_names()
        shared = set(left_cols) & set(right_cols)
        result = []
        for lrow in left.rows:
            for rrow in right.rows:
                merged = {}
                for col in left_cols:
                    merged[f"{left.name}.{col}"] = lrow[col]
                    if col not in shared:
                        merged[col] = lrow[col]
                for col in right_cols:
                    merged[f"{right.name}.{col}"] = rrow[col]
                    if col not in shared:
                        merged[col] = rrow[col]
                if _compare(on.op, merged.get(on.left), merged.get(on.right)):
                    result.append(merged)
        return result

    def _resolve_join_column(self, left, right, name):
        if "." in name:
            qualifier, col = name.split(".", 1)
            if qualifier == left.name:
                return left.column_type(col)
            if qualifier == right.name:
                return right.column_type(col)
            raise NanosqlError(f"unknown table qualifier {qualifier!r}")
        left_has = name in left.column_names()
        right_has = name in right.column_names()
        if left_has and right_has:
            raise NanosqlError(f"column {name!r} is ambiguous between {left.name!r} and {right.name!r}")
        if left_has:
            return left.column_type(name)
        if right_has:
            return right.column_type(name)
        raise NanosqlError(f"no such column {name!r}")

    def _exec_Select(self, stmt):
        table = self._table(stmt.table)
        if stmt.join is not None:
            right = self._table(stmt.join.table)
            rows_universe = self._join_rows(table, right, stmt.join.on)
            column_universe = [f"{table.name}.{c}" for c in table.column_names()] + [
                f"{right.name}.{c}" for c in right.column_names()
            ]
            validate_col = lambda name: self._resolve_join_column(table, right, name)
        else:
            rows_universe = table.rows
            column_universe = table.column_names()
            validate_col = table.column_type
            if (
                isinstance(stmt.where, Cmp)
                and stmt.where.op == "="
                and stmt.where.column in table.indexed_columns
            ):
                rows_universe = table.indexes[stmt.where.column].get(stmt.where.value, [])

        if stmt.group_by is not None or any(isinstance(c, AggCall) for c in stmt.columns):
            return self._exec_select_aggregate(stmt, rows_universe, column_universe, validate_col)
        columns = column_universe if stmt.columns == ["*"] else stmt.columns
        for name in columns:
            validate_col(name)
        matches = [row for row in rows_universe if _eval_where(stmt.where, row)]
        if stmt.order_by is not None:
            col, direction = stmt.order_by
            validate_col(col)
            matches = sorted(matches, key=lambda r: (r[col] is None, r[col]), reverse=(direction == "DESC"))
        if stmt.limit is not None:
            matches = matches[: stmt.limit]
        rows = [{name: row[name] for name in columns} for row in matches]
        return {"kind": "rows", "columns": columns, "rows": rows}

    def _exec_select_aggregate(self, stmt, rows_universe, column_universe, validate_col):
        for col in stmt.columns:
            if isinstance(col, AggCall):
                if col.column != "*":
                    validate_col(col.column)
            elif col != stmt.group_by:
                raise NanosqlError(
                    f"column {col!r} must appear in GROUP BY or be used in an aggregate function"
                )
        if stmt.group_by is not None:
            validate_col(stmt.group_by)
        matches = [row for row in rows_universe if _eval_where(stmt.where, row)]
        groups = {}
        order = []
        if stmt.group_by is not None:
            for row in matches:
                key = row[stmt.group_by]
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append(row)
        else:
            order = [None]
            groups = {None: matches}
        columns = [col.label() if isinstance(col, AggCall) else col for col in stmt.columns]
        result_rows = []
        for key in order:
            grouped_rows = groups[key]
            out = {}
            for col in stmt.columns:
                if isinstance(col, AggCall):
                    out[col.label()] = _compute_aggregate(col, grouped_rows)
                else:
                    out[col] = key
            result_rows.append(out)
        if stmt.order_by is not None:
            col, direction = stmt.order_by
            if col not in columns:
                raise NanosqlError(f"cannot ORDER BY {col!r}: not in the selected columns")
            result_rows = sorted(
                result_rows, key=lambda r: (r[col] is None, r[col]), reverse=(direction == "DESC")
            )
        if stmt.limit is not None:
            result_rows = result_rows[: stmt.limit]
        return {"kind": "rows", "columns": columns, "rows": result_rows}

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
        if count and table.indexed_columns:
            table.rebuild_all_indexes()
        return {"kind": "ok", "message": f"{count} row(s) updated"}

    def _exec_Delete(self, stmt):
        table = self._table(stmt.table)
        before = len(table.rows)
        table.rows = [row for row in table.rows if not _eval_where(stmt.where, row)]
        count = before - len(table.rows)
        if count and table.indexed_columns:
            table.rebuild_all_indexes()
        return {"kind": "ok", "message": f"{count} row(s) deleted"}

    def to_dict(self):
        return {"tables": {name: table.to_dict() for name, table in self.tables.items()}}

    @classmethod
    def from_dict(cls, data):
        db = cls()
        for name, table_data in data.get("tables", {}).items():
            db.tables[name] = Table.from_dict(name, table_data)
        return db
