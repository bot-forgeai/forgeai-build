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


def test_generation_starts_at_zero_and_bumps_on_compact(db_path):
    with KVStore(db_path) as store:
        assert store.generation == 0
        store.put("a", "1")
        store.compact()
        assert store.generation == 1
        store.compact()
        assert store.generation == 2


def test_generation_persists_across_reopen(db_path):
    with KVStore(db_path) as store:
        store.put("a", "1")
        store.compact()
    with KVStore(db_path) as store:
        assert store.generation == 1


def test_clear_empties_store_and_resets_log_file(db_path):
    with KVStore(db_path) as store:
        store.put("a", "1")
        store.put("b", "2")
        store.clear()
        assert len(store) == 0
        assert "a" not in store
        store.put("c", "3")
        assert store.get("c") == "3"

    # cleared state survives a reopen too — the log file was actually
    # truncated, not just the in-memory dict.
    with KVStore(db_path) as store:
        assert store.keys() == ["c"]


def test_prefix(db_path):
    with KVStore(db_path) as store:
        store.put("user:1", "ada")
        store.put("user:2", "bob")
        store.put("group:1", "admins")
        assert store.prefix("user:") == [("user:1", "ada"), ("user:2", "bob")]
        assert store.prefix("nope:") == []


def test_fsync_always_calls_os_fsync(db_path, monkeypatch):
    calls = []
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append(fd))
    with KVStore(db_path, fsync="always") as store:
        store.put("a", 1)
        store.put("b", 2)
        store.delete("a")
    assert len(calls) == 3


def test_fsync_never_skips_os_fsync(db_path, monkeypatch):
    calls = []
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append(fd))
    with KVStore(db_path, fsync="never") as store:
        store.put("a", 1)
        store.put("b", 2)
    assert calls == []
    # still durable across a normal reopen since flush() still happens
    with KVStore(db_path, fsync="never") as store:
        assert store.get("a") == 1
        assert store.get("b") == 2


def test_fsync_never_compact_skips_os_fsync(db_path, monkeypatch):
    with KVStore(db_path, fsync="never") as store:
        store.put("a", 1)
        store.put("a", 2)
    calls = []
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append(fd))
    with KVStore(db_path, fsync="never") as store:
        store.compact()
    assert calls == []


def test_invalid_fsync_value_rejected(db_path):
    with pytest.raises(ValueError):
        KVStore(db_path, fsync="sometimes")


def test_range(db_path):
    with KVStore(db_path) as store:
        for k in ["a", "b", "c", "d", "e"]:
            store.put(k, k.upper())
        assert store.range("b", "d") == [("b", "B"), ("c", "C"), ("d", "D")]
        assert store.range(start="c") == [("c", "C"), ("d", "D"), ("e", "E")]
        assert store.range(end="b") == [("a", "A"), ("b", "B")]
        assert store.range() == store.items()


def test_offset_grows_with_writes(db_path):
    with KVStore(db_path) as store:
        zero = store.offset()
        assert zero == 0
        store.put("a", "1")
        after_one = store.offset()
        assert after_one > zero
        store.put("b", "2")
        assert store.offset() > after_one


def test_records_since_returns_only_new_records(db_path):
    with KVStore(db_path) as store:
        store.put("a", "1")
        cursor = store.offset()
        store.put("b", "2")
        store.delete("a")
        records, new_offset = store.records_since(cursor)
        assert records == [
            {"op": "put", "key": "b", "value": "2"},
            {"op": "delete", "key": "a", "value": None},
        ]
        assert new_offset == store.offset()


def test_records_since_zero_returns_everything(db_path):
    with KVStore(db_path) as store:
        store.put("a", "1")
        store.put("b", "2")
        records, offset = store.records_since(0)
        assert [r["key"] for r in records] == ["a", "b"]
        assert offset == store.offset()


def test_records_since_current_offset_is_empty(db_path):
    with KVStore(db_path) as store:
        store.put("a", "1")
        cursor = store.offset()
        records, offset = store.records_since(cursor)
        assert records == []
        assert offset == cursor
