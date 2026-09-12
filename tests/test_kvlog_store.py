import os

import pytest

from kvlog.log import encode_record
from kvlog.store import KVStore


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


def test_put_get(db_path):
    with KVStore(db_path) as store:
        store.put("name", "ada")
        assert store.get("name") == "ada"
        assert "name" in store
        assert store.get("missing") is None
        assert store.get("missing", "default") == "default"


def test_delete(db_path):
    with KVStore(db_path) as store:
        store.put("x", 1)
        assert store.delete("x") is True
        assert "x" not in store
        assert store.delete("x") is False


def test_keys_and_items_sorted(db_path):
    with KVStore(db_path) as store:
        store.put("b", 2)
        store.put("a", 1)
        store.put("c", 3)
        assert store.keys() == ["a", "b", "c"]
        assert store.items() == [("a", 1), ("b", 2), ("c", 3)]


def test_overwrite_keeps_latest_value(db_path):
    with KVStore(db_path) as store:
        store.put("k", "first")
        store.put("k", "second")
        assert store.get("k") == "second"
        assert len(store) == 1


def test_reopen_replays_log(db_path):
    with KVStore(db_path) as store:
        store.put("a", 1)
        store.put("b", 2)
        store.delete("a")

    with KVStore(db_path) as store:
        assert store.get("a") is None
        assert store.get("b") == 2
        assert store.keys() == ["b"]


def test_reopen_after_simulated_crash_drops_truncated_tail(db_path):
    with KVStore(db_path) as store:
        store.put("a", "1")

    # append a partially-written record directly to simulate a crash
    # mid-append, bypassing the store's own flush-on-write path
    full_record = encode_record("put", "b", "2")
    with open(db_path, "ab") as f:
        f.write(full_record[: len(full_record) // 2])

    with KVStore(db_path) as store:
        assert store.get("a") == "1"
        assert "b" not in store
        assert store.keys() == ["a"]


def test_compact_reduces_log_size_and_preserves_state(db_path):
    with KVStore(db_path) as store:
        for i in range(20):
            store.put("k", i)  # 20 overwrites of the same key
        store.put("other", "value")
        size_before = os.path.getsize(db_path)
        store.compact()
        size_after = os.path.getsize(db_path)
        assert size_after < size_before
        assert store.get("k") == 19
        assert store.get("other") == "value"

    # compacted state survives a reopen too
    with KVStore(db_path) as store:
        assert store.get("k") == 19
        assert store.keys() == ["k", "other"]


def test_compact_drops_deleted_keys(db_path):
    with KVStore(db_path) as store:
        store.put("gone", "x")
        store.delete("gone")
        store.put("stays", "y")
        store.compact()

    with KVStore(db_path) as store:
        assert "gone" not in store
        assert store.get("stays") == "y"
