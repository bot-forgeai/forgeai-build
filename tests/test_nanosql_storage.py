from nanosql.engine import Database
from nanosql.storage import load, save


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "db.json"
    db = Database()
    db.execute("CREATE TABLE t (id INT, name TEXT)")
    db.execute("INSERT INTO t VALUES (1, 'Ada')")
    save(db, str(path))

    loaded = load(str(path))
    rows = loaded.execute("SELECT * FROM t")["rows"]
    assert rows == [{"id": 1, "name": "Ada"}]


def test_load_missing_file_returns_empty_database(tmp_path):
    db = load(str(tmp_path / "nope.json"))
    assert db.to_dict() == {"tables": {}}


def test_save_leaves_no_temp_file_behind(tmp_path):
    path = tmp_path / "db.json"
    db = Database()
    db.execute("CREATE TABLE t (id INT)")
    save(db, str(path))
    leftover = [p for p in tmp_path.iterdir() if p.name != "db.json"]
    assert leftover == []


def test_save_does_not_corrupt_existing_file_content_shape(tmp_path):
    path = tmp_path / "db.json"
    db = Database()
    db.execute("CREATE TABLE t (id INT)")
    db.execute("INSERT INTO t VALUES (1)")
    save(db, str(path))
    with open(path) as f:
        first = f.read()
    db.execute("INSERT INTO t VALUES (2)")
    save(db, str(path))
    with open(path) as f:
        second = f.read()
    assert first != second
    loaded = load(str(path))
    assert len(loaded.execute("SELECT * FROM t")["rows"]) == 2
