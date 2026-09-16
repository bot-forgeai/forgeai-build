import pytest

from nanosql.ast_nodes import AggCall, BoolOp, Cmp, CreateIndex, CreateTable, Delete, Insert, Select, Update
from nanosql.parser import ParseError, parse


def test_parse_create_table():
    stmt = parse("CREATE TABLE users (id INT, name TEXT, score REAL)")
    assert isinstance(stmt, CreateTable)
    assert stmt.table == "users"
    assert stmt.columns == [("id", "INT"), ("name", "TEXT"), ("score", "REAL")]


def test_parse_create_index():
    stmt = parse("CREATE INDEX idx_email ON users (email)")
    assert isinstance(stmt, CreateIndex)
    assert stmt.index_name == "idx_email"
    assert stmt.table == "users"
    assert stmt.column == "email"


def test_parse_insert_with_explicit_columns():
    stmt = parse("INSERT INTO users (id, name) VALUES (1, 'Ada')")
    assert isinstance(stmt, Insert)
    assert stmt.columns == ["id", "name"]
    assert stmt.values == [1, "Ada"]


def test_parse_insert_without_columns():
    stmt = parse("INSERT INTO users VALUES (1, 'Ada', 9.5)")
    assert stmt.columns is None
    assert stmt.values == [1, "Ada", 9.5]


def test_parse_insert_null_and_bool_literals():
    stmt = parse("INSERT INTO t VALUES (NULL, TRUE, FALSE)")
    assert stmt.values == [None, True, False]


def test_parse_select_star():
    stmt = parse("SELECT * FROM users")
    assert isinstance(stmt, Select)
    assert stmt.columns == ["*"]
    assert stmt.table == "users"
    assert stmt.where is None


def test_parse_select_columns():
    stmt = parse("SELECT id, name FROM users")
    assert stmt.columns == ["id", "name"]


def test_parse_select_where_comparison():
    stmt = parse("SELECT * FROM users WHERE age >= 18")
    assert isinstance(stmt.where, Cmp)
    assert stmt.where.column == "age"
    assert stmt.where.op == ">="
    assert stmt.where.value == 18


def test_parse_select_where_and_or_precedence():
    stmt = parse("SELECT * FROM t WHERE a = 1 AND b = 2 OR c = 3")
    where = stmt.where
    assert isinstance(where, BoolOp)
    assert where.op == "OR"
    assert isinstance(where.left, BoolOp)
    assert where.left.op == "AND"
    assert isinstance(where.right, Cmp)


def test_parse_select_order_by_and_limit():
    stmt = parse("SELECT * FROM t ORDER BY name DESC LIMIT 5")
    assert stmt.order_by == ("name", "DESC")
    assert stmt.limit == 5


def test_parse_select_order_by_default_asc():
    stmt = parse("SELECT * FROM t ORDER BY name")
    assert stmt.order_by == ("name", "ASC")


def test_parse_update():
    stmt = parse("UPDATE users SET score = 10, name = 'Bea' WHERE id = 1")
    assert isinstance(stmt, Update)
    assert stmt.assignments == [("score", 10), ("name", "Bea")]
    assert isinstance(stmt.where, Cmp)


def test_parse_delete():
    stmt = parse("DELETE FROM users WHERE id = 1")
    assert isinstance(stmt, Delete)
    assert stmt.table == "users"


def test_parse_delete_without_where():
    stmt = parse("DELETE FROM users")
    assert stmt.where is None


def test_parse_trailing_semicolon_ok():
    stmt = parse("SELECT * FROM t;")
    assert isinstance(stmt, Select)


def test_parse_unrecognized_statement_raises():
    with pytest.raises(ParseError):
        parse("DROP TABLE users")


def test_parse_missing_paren_raises():
    with pytest.raises(ParseError):
        parse("CREATE TABLE t id INT)")


def test_parse_trailing_garbage_raises():
    with pytest.raises(ParseError):
        parse("SELECT * FROM t garbage")


def test_parse_select_count_star():
    stmt = parse("SELECT COUNT(*) FROM t")
    assert len(stmt.columns) == 1
    agg = stmt.columns[0]
    assert isinstance(agg, AggCall)
    assert agg.func == "COUNT"
    assert agg.column == "*"
    assert agg.label() == "COUNT(*)"


def test_parse_select_aggregate_functions():
    stmt = parse("SELECT SUM(price), AVG(price), MIN(price), MAX(price) FROM t")
    funcs = [c.func for c in stmt.columns]
    assert funcs == ["SUM", "AVG", "MIN", "MAX"]
    assert all(c.column == "price" for c in stmt.columns)


def test_parse_select_group_by():
    stmt = parse("SELECT category, COUNT(*) FROM items GROUP BY category")
    assert stmt.group_by == "category"
    assert stmt.columns[0] == "category"
    assert isinstance(stmt.columns[1], AggCall)


def test_parse_select_group_by_with_order_and_limit():
    stmt = parse("SELECT category, SUM(price) FROM items GROUP BY category ORDER BY category DESC LIMIT 3")
    assert stmt.group_by == "category"
    assert stmt.order_by == ("category", "DESC")
    assert stmt.limit == 3


def test_parse_select_no_group_by_defaults_none():
    stmt = parse("SELECT * FROM t")
    assert stmt.group_by is None


def test_parse_select_no_join_defaults_none():
    stmt = parse("SELECT * FROM t")
    assert stmt.join is None


def test_parse_select_join_on():
    stmt = parse("SELECT * FROM orders JOIN users ON orders.user_id = users.id")
    assert stmt.join is not None
    assert stmt.join.table == "users"
    assert stmt.join.on.left == "orders.user_id"
    assert stmt.join.on.op == "="
    assert stmt.join.on.right == "users.id"


def test_parse_qualified_column_in_select_list():
    stmt = parse("SELECT orders.id, users.name FROM orders JOIN users ON orders.user_id = users.id")
    assert stmt.columns == ["orders.id", "users.name"]


def test_parse_qualified_column_in_where():
    stmt = parse("SELECT * FROM orders JOIN users ON orders.user_id = users.id WHERE users.name = 'Ada'")
    assert stmt.where.column == "users.name"
    assert stmt.where.value == "Ada"


def test_parse_join_missing_on_raises():
    with pytest.raises(ParseError):
        parse("SELECT * FROM orders JOIN users")
