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
    assert load_cursor(db_path) == (0, None)
    save_cursor(db_path, 42, 0)
    assert load_cursor(db_path) == (42, 0)
    save_cursor(db_path, 100, 2)
    assert load_cursor(db_path) == (100, 2)


def test_load_cursor_old_format_has_no_generation(tmp_path):
    # A cursor file written before generation tracking existed has just
    # a bare offset — must still parse, with generation reported as None.
    db_path = str(tmp_path / "replica.db")
    with open(db_path + ".replica_offset", "w") as f:
        f.write("77")
    assert load_cursor(db_path) == (77, None)


def test_sync_once_applies_new_records_and_advances_cursor(running_leader, tmp_path):
    host, port, leader_store = running_leader
    leader_store.put("a", "1")
    with KVStore(str(tmp_path / "replica.db")) as replica_store:
        cursor, generation = sync_once(replica_store, host, port, 0, None)
        assert replica_store.get("a") == "1"
        assert cursor == leader_store.offset()
        assert generation == 0

        # A second sync at the new cursor with no new leader writes applies nothing.
        cursor2, generation2 = sync_once(replica_store, host, port, cursor, generation)
        assert cursor2 == cursor
        assert generation2 == generation


def test_sync_once_resyncs_from_scratch_after_leader_compacts(running_leader, tmp_path):
    host, port, leader_store = running_leader
    leader_store.put("a", "1")
    leader_store.put("b", "2")
    leader_store.delete("a")

    with KVStore(str(tmp_path / "replica.db")) as replica_store:
        cursor, generation = sync_once(replica_store, host, port, 0, None)
        assert "a" not in replica_store
        assert replica_store.get("b") == "2"

        # Compaction rewrites the leader's log from offset 0 and bumps its
        # generation. A replica syncing with its old (now-invalid) cursor
        # must detect this via the generation mismatch, not silently apply
        # a diff against the rewritten file.
        leader_store.compact()
        leader_store.put("c", "3")

        cursor2, generation2 = sync_once(replica_store, host, port, cursor, generation)
        assert generation2 == leader_store.generation
        assert replica_store.get("b") == "2"
        assert replica_store.get("c") == "3"
        assert "a" not in replica_store


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
    cursor, generation = load_cursor(db_path)
    assert cursor == leader_store.offset()
    assert generation == leader_store.generation


def test_run_replica_reflects_deletes(running_leader, tmp_path):
    host, port, leader_store = running_leader
    leader_store.put("a", "1")
    leader_store.delete("a")

    db_path = str(tmp_path / "replica.db")
    stop_event = threading.Event()
    run_replica(db_path, host, port, stop_event=stop_event, sleep_fn=lambda s: stop_event.set())

    with KVStore(db_path) as replica_store:
        assert "a" not in replica_store
