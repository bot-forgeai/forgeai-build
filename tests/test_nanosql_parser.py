import pytest

from nanosql.ast_nodes import BoolOp, Cmp, CreateTable, Delete, Insert, Select, Update
from nanosql.parser import ParseError, parse


def test_parse_create_table():
    stmt = parse("CREATE TABLE users (id INT, name TEXT, score REAL)")
    assert isinstance(stmt, CreateTable)
    assert stmt.table == "users"
    assert stmt.columns == [("id", "INT"), ("name", "TEXT"), ("score", "REAL")]


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
