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


def test_select_where_like_prefix():
    db = make_users_db()
    rows = db.execute("SELECT name FROM users WHERE name LIKE 'A%'")["rows"]
    assert rows == [{"name": "Ada"}]


def test_select_where_like_underscore_wildcard():
    db = make_users_db()
    rows = db.execute("SELECT name FROM users WHERE name LIKE '_da'")["rows"]
    assert rows == [{"name": "Ada"}]


def test_select_where_like_suffix():
    db = make_users_db()
    rows = db.execute("SELECT name FROM users WHERE name LIKE '%a'")["rows"]
    assert {r["name"] for r in rows} == {"Ada", "Bea"}


def test_select_where_like_no_match():
    db = make_users_db()
    rows = db.execute("SELECT name FROM users WHERE name LIKE 'Z%'")["rows"]
    assert rows == []


def test_select_where_like_full_match_not_substring():
    db = make_users_db()
    rows = db.execute("SELECT name FROM users WHERE name LIKE 'd'")["rows"]
    assert rows == []


def test_select_where_like_against_null_is_false():
    db = Database()
    db.execute("CREATE TABLE t (a TEXT)")
    db.execute("INSERT INTO t VALUES (NULL)")
    rows = db.execute("SELECT * FROM t WHERE a LIKE '%x%'")["rows"]
    assert rows == []


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


def make_orders_db():
    db = Database()
    db.execute("CREATE TABLE orders (id INT, category TEXT, price REAL)")
    db.execute("INSERT INTO orders VALUES (1, 'fruit', 3.0)")
    db.execute("INSERT INTO orders VALUES (2, 'fruit', 5.0)")
    db.execute("INSERT INTO orders VALUES (3, 'veg', 2.0)")
    db.execute("INSERT INTO orders VALUES (4, 'veg', 4.0)")
    db.execute("INSERT INTO orders VALUES (5, 'veg', 6.0)")
    return db


def test_count_star_whole_table():
    db = make_orders_db()
    rows = db.execute("SELECT COUNT(*) FROM orders")["rows"]
    assert rows == [{"COUNT(*)": 5}]


def test_count_star_with_where():
    db = make_orders_db()
    rows = db.execute("SELECT COUNT(*) FROM orders WHERE category = 'veg'")["rows"]
    assert rows == [{"COUNT(*)": 3}]


def test_count_star_no_matches_returns_zero_not_empty():
    db = make_orders_db()
    rows = db.execute("SELECT COUNT(*) FROM orders WHERE id = 99")["rows"]
    assert rows == [{"COUNT(*)": 0}]


def test_sum_avg_min_max_whole_table():
    db = make_orders_db()
    rows = db.execute("SELECT SUM(price), AVG(price), MIN(price), MAX(price) FROM orders")["rows"]
    assert rows == [{"SUM(price)": 20.0, "AVG(price)": 4.0, "MIN(price)": 2.0, "MAX(price)": 6.0}]


def test_sum_with_no_matching_rows_is_zero():
    db = make_orders_db()
    rows = db.execute("SELECT SUM(price) FROM orders WHERE id = 99")["rows"]
    assert rows == [{"SUM(price)": 0}]


def test_min_max_with_no_matching_rows_is_none():
    db = make_orders_db()
    rows = db.execute("SELECT MIN(price), MAX(price) FROM orders WHERE id = 99")["rows"]
    assert rows == [{"MIN(price)": None, "MAX(price)": None}]


def test_group_by_with_count_and_sum():
    db = make_orders_db()
    result = db.execute("SELECT category, COUNT(*), SUM(price) FROM orders GROUP BY category ORDER BY category")
    assert result["columns"] == ["category", "COUNT(*)", "SUM(price)"]
    assert result["rows"] == [
        {"category": "fruit", "COUNT(*)": 2, "SUM(price)": 8.0},
        {"category": "veg", "COUNT(*)": 3, "SUM(price)": 12.0},
    ]


def test_group_by_with_where():
    db = make_orders_db()
    rows = db.execute(
        "SELECT category, COUNT(*) FROM orders WHERE price > 3 GROUP BY category ORDER BY category"
    )["rows"]
    assert rows == [
        {"category": "fruit", "COUNT(*)": 1},
        {"category": "veg", "COUNT(*)": 2},
    ]


def test_group_by_with_limit():
    db = make_orders_db()
    rows = db.execute("SELECT category, COUNT(*) FROM orders GROUP BY category ORDER BY category LIMIT 1")["rows"]
    assert rows == [{"category": "fruit", "COUNT(*)": 2}]


def test_plain_column_not_in_group_by_raises():
    db = make_orders_db()
    with pytest.raises(NanosqlError):
        db.execute("SELECT id, COUNT(*) FROM orders GROUP BY category")


def test_aggregate_unknown_column_raises():
    db = make_orders_db()
    with pytest.raises(NanosqlError):
        db.execute("SELECT SUM(nope) FROM orders")


def test_to_dict_and_from_dict_round_trip():
    db = make_users_db()
    restored = Database.from_dict(db.to_dict())
    rows = restored.execute("SELECT * FROM users ORDER BY id")["rows"]
    assert rows == [
        {"id": 1, "name": "Ada", "age": 36},
        {"id": 2, "name": "Bea", "age": 24},
        {"id": 3, "name": "Cid", "age": 42},
    ]


def make_users_orders_db():
    db = make_users_db()
    db.execute("CREATE TABLE orders (id INT, user_id INT, item TEXT)")
    db.execute("INSERT INTO orders VALUES (1, 1, 'Widget')")
    db.execute("INSERT INTO orders VALUES (2, 1, 'Gadget')")
    db.execute("INSERT INTO orders VALUES (3, 2, 'Widget')")
    db.execute("INSERT INTO orders VALUES (4, 99, 'Orphan')")  # no matching user
    return db


def test_join_basic_inner_join():
    db = make_users_orders_db()
    result = db.execute(
        "SELECT orders.item, users.name FROM orders JOIN users ON orders.user_id = users.id "
        "ORDER BY orders.id"
    )
    assert result["rows"] == [
        {"orders.item": "Widget", "users.name": "Ada"},
        {"orders.item": "Gadget", "users.name": "Ada"},
        {"orders.item": "Widget", "users.name": "Bea"},
    ]


def test_join_excludes_unmatched_rows():
    db = make_users_orders_db()
    result = db.execute("SELECT * FROM orders JOIN users ON orders.user_id = users.id")
    # 4 orders total, but the orphan order (user_id 99) has no matching user
    assert len(result["rows"]) == 3


def test_join_unqualified_column_resolves_when_unambiguous():
    db = make_users_orders_db()
    result = db.execute(
        "SELECT item, name FROM orders JOIN users ON orders.user_id = users.id WHERE name = 'Ada'"
    )
    assert result["rows"] == [
        {"item": "Widget", "name": "Ada"},
        {"item": "Gadget", "name": "Ada"},
    ]


def test_join_ambiguous_unqualified_column_raises():
    db = make_users_orders_db()
    with pytest.raises(NanosqlError):
        db.execute("SELECT id FROM orders JOIN users ON orders.user_id = users.id")


def test_join_star_uses_qualified_column_names():
    db = make_users_orders_db()
    result = db.execute("SELECT * FROM orders JOIN users ON orders.user_id = users.id LIMIT 1")
    assert result["columns"] == ["orders.id", "orders.user_id", "orders.item", "users.id", "users.name", "users.age"]


def test_join_with_where_on_joined_table():
    db = make_users_orders_db()
    result = db.execute(
        "SELECT orders.item FROM orders JOIN users ON orders.user_id = users.id WHERE users.age > 30"
    )
    assert result["rows"] == [{"orders.item": "Widget"}, {"orders.item": "Gadget"}]


def test_join_unknown_qualifier_raises():
    db = make_users_orders_db()
    with pytest.raises(NanosqlError):
        db.execute("SELECT nope.id FROM orders JOIN users ON orders.user_id = users.id")


def test_join_with_group_by_aggregate():
    db = make_users_orders_db()
    result = db.execute(
        "SELECT users.name, COUNT(*) FROM orders JOIN users ON orders.user_id = users.id "
        "GROUP BY users.name ORDER BY users.name"
    )
    assert result["rows"] == [
        {"users.name": "Ada", "COUNT(*)": 2},
        {"users.name": "Bea", "COUNT(*)": 1},
    ]


def test_create_index_on_missing_table_raises():
    db = Database()
    with pytest.raises(NanosqlError):
        db.execute("CREATE INDEX idx_id ON nope (id)")


def test_create_index_on_missing_column_raises():
    db = make_users_db()
    with pytest.raises(NanosqlError):
        db.execute("CREATE INDEX idx_nope ON users (nope)")


def test_select_equality_uses_index_after_create():
    db = make_users_db()
    db.execute("CREATE INDEX idx_name ON users (name)")
    result = db.execute("SELECT * FROM users WHERE name = 'Bea'")
    assert result["rows"] == [{"id": 2, "name": "Bea", "age": 24}]


def test_create_index_on_existing_rows_finds_them():
    db = make_users_db()
    db.execute("CREATE INDEX idx_age ON users (age)")
    result = db.execute("SELECT name FROM users WHERE age = 42")
    assert result["rows"] == [{"name": "Cid"}]


def test_index_stays_correct_after_insert():
    db = make_users_db()
    db.execute("CREATE INDEX idx_name ON users (name)")
    db.execute("INSERT INTO users VALUES (4, 'Dee', 19)")
    result = db.execute("SELECT * FROM users WHERE name = 'Dee'")
    assert result["rows"] == [{"id": 4, "name": "Dee", "age": 19}]


def test_index_stays_correct_after_update():
    db = make_users_db()
    db.execute("CREATE INDEX idx_name ON users (name)")
    db.execute("UPDATE users SET name = 'Zed' WHERE id = 2")
    assert db.execute("SELECT * FROM users WHERE name = 'Bea'")["rows"] == []
    assert db.execute("SELECT * FROM users WHERE name = 'Zed'")["rows"] == [
        {"id": 2, "name": "Zed", "age": 24}
    ]


def test_index_stays_correct_after_delete():
    db = make_users_db()
    db.execute("CREATE INDEX idx_name ON users (name)")
    db.execute("DELETE FROM users WHERE id = 2")
    assert db.execute("SELECT * FROM users WHERE name = 'Bea'")["rows"] == []


def test_index_lookup_with_no_match_returns_empty():
    db = make_users_db()
    db.execute("CREATE INDEX idx_name ON users (name)")
    result = db.execute("SELECT * FROM users WHERE name = 'Nope'")
    assert result["rows"] == []


def test_indexed_equality_with_group_by_aggregate():
    db = make_users_db()
    db.execute("INSERT INTO users VALUES (4, 'Ada', 50)")
    db.execute("CREATE INDEX idx_name ON users (name)")
    result = db.execute("SELECT name, COUNT(*) FROM users WHERE name = 'Ada' GROUP BY name")
    assert result["rows"] == [{"name": "Ada", "COUNT(*)": 2}]


def test_to_dict_and_from_dict_round_trip_preserves_index():
    db = make_users_db()
    db.execute("CREATE INDEX idx_name ON users (name)")
    data = db.to_dict()
    restored = Database.from_dict(data)
    result = restored.execute("SELECT * FROM users WHERE name = 'Cid'")
    assert result["rows"] == [{"id": 3, "name": "Cid", "age": 42}]
    assert "name" in restored.tables["users"].indexed_columns


def test_commit_persists_changes_visible_after():
    db = make_users_db()
    db.execute("BEGIN")
    db.execute("INSERT INTO users VALUES (4, 'Dee', 30)")
    db.execute("COMMIT")
    assert not db.in_transaction()
    rows = db.execute("SELECT * FROM users")["rows"]
    assert len(rows) == 4


def test_rollback_discards_changes_made_since_begin():
    db = make_users_db()
    db.execute("BEGIN")
    db.execute("INSERT INTO users VALUES (4, 'Dee', 30)")
    db.execute("DELETE FROM users WHERE name = 'Ada'")
    db.execute("ROLLBACK")
    assert not db.in_transaction()
    rows = db.execute("SELECT * FROM users")["rows"]
    assert len(rows) == 3
    assert any(r["name"] == "Ada" for r in rows)


def test_rollback_restores_index_state_too():
    db = make_users_db()
    db.execute("CREATE INDEX idx_name ON users (name)")
    db.execute("BEGIN")
    db.execute("INSERT INTO users VALUES (4, 'Dee', 30)")
    db.execute("ROLLBACK")
    result = db.execute("SELECT * FROM users WHERE name = 'Dee'")
    assert result["rows"] == []
    result = db.execute("SELECT * FROM users WHERE name = 'Ada'")
    assert len(result["rows"]) == 1


def test_nested_begin_raises():
    db = make_users_db()
    db.execute("BEGIN")
    with pytest.raises(NanosqlError):
        db.execute("BEGIN")


def test_commit_without_begin_raises():
    db = make_users_db()
    with pytest.raises(NanosqlError):
        db.execute("COMMIT")


def test_rollback_without_begin_raises():
    db = make_users_db()
    with pytest.raises(NanosqlError):
        db.execute("ROLLBACK")


def test_in_transaction_reflects_state():
    db = make_users_db()
    assert not db.in_transaction()
    db.execute("BEGIN")
    assert db.in_transaction()
    db.execute("COMMIT")
    assert not db.in_transaction()


def test_execute_script_runs_statements_in_order():
    db = Database()
    results = db.execute_script(
        "CREATE TABLE t (id INT); INSERT INTO t VALUES (1); INSERT INTO t VALUES (2);"
    )
    assert len(results) == 3
    rows = db.execute("SELECT * FROM t")["rows"]
    assert len(rows) == 2


def test_execute_script_transaction_atomic_via_begin_commit():
    db = Database()
    db.execute("CREATE TABLE t (id INT)")
    db.execute_script("BEGIN; INSERT INTO t VALUES (1); INSERT INTO t VALUES (2); COMMIT;")
    assert not db.in_transaction()
    assert len(db.execute("SELECT * FROM t")["rows"]) == 2


def test_execute_script_rollback_leaves_no_trace():
    db = Database()
    db.execute("CREATE TABLE t (id INT)")
    db.execute_script("BEGIN; INSERT INTO t VALUES (1); ROLLBACK;")
    assert len(db.execute("SELECT * FROM t")["rows"]) == 0


def test_execute_script_stops_at_first_error_without_running_rest():
    db = Database()
    db.execute("CREATE TABLE t (id INT)")
    with pytest.raises(NanosqlError):
        db.execute_script("INSERT INTO t VALUES (1); SELECT * FROM nope; INSERT INTO t VALUES (2);")
    # first statement's effect is still in memory even though the script failed
    assert len(db.execute("SELECT * FROM t")["rows"]) == 1
