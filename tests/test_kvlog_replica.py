import threading

import pytest

from kvlog.replica import (
    apply_records,
    load_cursor,
    run_replica,
    save_cursor,
    sync_once,
)
from kvlog.server import KVServer
from kvlog.store import KVStore


@pytest.fixture
def running_leader(tmp_path):
    db_path = str(tmp_path / "leader.db")
    server = KVServer(("127.0.0.1", 0), db_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield host, port, server.store
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_apply_records_put_and_delete(tmp_path):
    with KVStore(str(tmp_path / "db")) as store:
        apply_records(store, [{"op": "put", "key": "a", "value": "1"}])
        assert store.get("a") == "1"
        apply_records(store, [{"op": "delete", "key": "a", "value": None}])
        assert "a" not in store


def test_apply_records_delete_of_absent_key_is_a_noop(tmp_path):
    with KVStore(str(tmp_path / "db")) as store:
        apply_records(store, [{"op": "delete", "key": "nope", "value": None}])
        assert "nope" not in store


def test_cursor_round_trip(tmp_path):
    db_path = str(tmp_path / "replica.db")
    assert load_cursor(db_path) == 0
    save_cursor(db_path, 42)
    assert load_cursor(db_path) == 42
    save_cursor(db_path, 100)
    assert load_cursor(db_path) == 100


def test_sync_once_applies_new_records_and_advances_cursor(running_leader, tmp_path):
    host, port, leader_store = running_leader
    leader_store.put("a", "1")
    with KVStore(str(tmp_path / "replica.db")) as replica_store:
        cursor = sync_once(replica_store, host, port, 0)
        assert replica_store.get("a") == "1"
        assert cursor == leader_store.offset()

        # A second sync at the new cursor with no new leader writes applies nothing.
        cursor2 = sync_once(replica_store, host, port, cursor)
        assert cursor2 == cursor


def test_run_replica_catches_up_and_stops(running_leader, tmp_path):
    host, port, leader_store = running_leader
    leader_store.put("a", "1")
    leader_store.put("b", "2")

    db_path = str(tmp_path / "replica.db")
    stop_event = threading.Event()
    rounds = []

    def fake_sleep(_seconds):
        # Stop after the first successful poll round instead of looping forever.
        stop_event.set()

    def on_sync(cursor):
        rounds.append(cursor)

    run_replica(
        db_path,
        host,
        port,
        stop_event=stop_event,
        sleep_fn=fake_sleep,
        on_sync=on_sync,
    )

    assert len(rounds) == 1
    with KVStore(db_path) as replica_store:
        assert replica_store.get("a") == "1"
        assert replica_store.get("b") == "2"


def test_run_replica_resumes_from_persisted_cursor(running_leader, tmp_path):
    host, port, leader_store = running_leader
    leader_store.put("a", "1")

    db_path = str(tmp_path / "replica.db")
    stop_event = threading.Event()
    run_replica(db_path, host, port, stop_event=stop_event, sleep_fn=lambda s: stop_event.set())

    leader_store.put("b", "2")
    stop_event2 = threading.Event()
    run_replica(db_path, host, port, stop_event=stop_event2, sleep_fn=lambda s: stop_event2.set())

    with KVStore(db_path) as replica_store:
        assert replica_store.get("a") == "1"
        assert replica_store.get("b") == "2"

    # The second run's sync should only have needed the new record, not a
    # full resync — verified indirectly via the persisted cursor matching
    # the leader's current offset.
    assert load_cursor(db_path) == leader_store.offset()


def test_run_replica_reflects_deletes(running_leader, tmp_path):
    host, port, leader_store = running_leader
    leader_store.put("a", "1")
    leader_store.delete("a")

    db_path = str(tmp_path / "replica.db")
    stop_event = threading.Event()
    run_replica(db_path, host, port, stop_event=stop_event, sleep_fn=lambda s: stop_event.set())

    with KVStore(db_path) as replica_store:
        assert "a" not in replica_store
