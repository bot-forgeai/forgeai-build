import pytest

from nanosql.engine import Database, NanosqlError


def make_users_db():
    db = Database()
    db.execute("CREATE TABLE users (id INT, name TEXT, age INT)")
    db.execute("INSERT INTO users VALUES (1, 'Ada', 36)")
    db.execute("INSERT INTO users VALUES (2, 'Bea', 24)")
    db.execute("INSERT INTO users VALUES (3, 'Cid', 42)")
    return db


def test_create_table_twice_raises():
    db = Database()
    db.execute("CREATE TABLE t (id INT)")
    with pytest.raises(NanosqlError):
        db.execute("CREATE TABLE t (id INT)")


def test_insert_and_select_all():
    db = make_users_db()
    result = db.execute("SELECT * FROM users")
    assert result["kind"] == "rows"
    assert result["columns"] == ["id", "name", "age"]
    assert len(result["rows"]) == 3
    assert result["rows"][0] == {"id": 1, "name": "Ada", "age": 36}


def test_insert_with_explicit_columns_defaults_missing_to_none():
    db = Database()
    db.execute("CREATE TABLE t (a INT, b INT)")
    db.execute("INSERT INTO t (a) VALUES (5)")
    rows = db.execute("SELECT * FROM t")["rows"]
    assert rows == [{"a": 5, "b": None}]


def test_insert_column_count_mismatch_raises():
    db = Database()
    db.execute("CREATE TABLE t (a INT, b INT)")
    with pytest.raises(NanosqlError):
        db.execute("INSERT INTO t VALUES (1)")


def test_insert_type_cast():
    db = Database()
    db.execute("CREATE TABLE t (a REAL)")
    db.execute("INSERT INTO t VALUES (5)")
    rows = db.execute("SELECT * FROM t")["rows"]
    assert rows == [{"a": 5.0}]


def test_select_specific_columns():
    db = make_users_db()
    result = db.execute("SELECT name FROM users")
    assert result["columns"] == ["name"]
    assert result["rows"] == [{"name": "Ada"}, {"name": "Bea"}, {"name": "Cid"}]


def test_select_where_equals():
    db = make_users_db()
    rows = db.execute("SELECT name FROM users WHERE id = 2")["rows"]
    assert rows == [{"name": "Bea"}]


def test_select_where_comparison_operators():
    db = make_users_db()
    rows = db.execute("SELECT name FROM users WHERE age >= 36")["rows"]
    assert {r["name"] for r in rows} == {"Ada", "Cid"}


def test_select_where_and():
    db = make_users_db()
    rows = db.execute("SELECT name FROM users WHERE age > 20 AND age < 40")["rows"]
    assert {r["name"] for r in rows} == {"Ada", "Bea"}


def test_select_where_or():
    db = make_users_db()
    rows = db.execute("SELECT name FROM users WHERE age = 24 OR age = 42")["rows"]
    assert {r["name"] for r in rows} == {"Bea", "Cid"}


def test_select_order_by_asc_and_desc():
    db = make_users_db()
    asc = db.execute("SELECT name FROM users ORDER BY age")["rows"]
    assert [r["name"] for r in asc] == ["Bea", "Ada", "Cid"]
    desc = db.execute("SELECT name FROM users ORDER BY age DESC")["rows"]
    assert [r["name"] for r in desc] == ["Cid", "Ada", "Bea"]


def test_select_limit():
    db = make_users_db()
    rows = db.execute("SELECT name FROM users ORDER BY age LIMIT 2")["rows"]
    assert [r["name"] for r in rows] == ["Bea", "Ada"]


def test_select_no_match_returns_empty():
    db = make_users_db()
    rows = db.execute("SELECT * FROM users WHERE id = 99")["rows"]
    assert rows == []


def test_select_unknown_table_raises():
    db = Database()
    with pytest.raises(NanosqlError):
        db.execute("SELECT * FROM nope")


def test_select_unknown_column_raises():
    db = make_users_db()
    with pytest.raises(NanosqlError):
        db.execute("SELECT nope FROM users")


def test_update_with_where():
    db = make_users_db()
    result = db.execute("UPDATE users SET age = 25 WHERE name = 'Bea'")
    assert result["message"] == "1 row(s) updated"
    rows = db.execute("SELECT age FROM users WHERE name = 'Bea'")["rows"]
    assert rows == [{"age": 25}]


def test_update_without_where_affects_all():
    db = make_users_db()
    db.execute("UPDATE users SET age = 0")
    rows = db.execute("SELECT age FROM users")["rows"]
    assert all(r["age"] == 0 for r in rows)


def test_delete_with_where():
    db = make_users_db()
    result = db.execute("DELETE FROM users WHERE name = 'Ada'")
    assert result["message"] == "1 row(s) deleted"
    rows = db.execute("SELECT name FROM users")["rows"]
    assert {r["name"] for r in rows} == {"Bea", "Cid"}


def test_delete_without_where_clears_table():
    db = make_users_db()
    db.execute("DELETE FROM users")
    assert db.execute("SELECT * FROM users")["rows"] == []


def test_syntax_error_wrapped_in_nanosql_error():
    db = Database()
    with pytest.raises(NanosqlError):
        db.execute("NOT VALID SQL")


def test_to_dict_and_from_dict_round_trip():
    db = make_users_db()
    restored = Database.from_dict(db.to_dict())
    rows = restored.execute("SELECT * FROM users ORDER BY id")["rows"]
    assert rows == [
        {"id": 1, "name": "Ada", "age": 36},
        {"id": 2, "name": "Bea", "age": 24},
        {"id": 3, "name": "Cid", "age": 42},
    ]
