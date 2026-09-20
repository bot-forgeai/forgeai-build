"""Leader/replica log shipping: a replica polls a leader's `sync` op for
records it hasn't applied yet, applies them to its own local KVStore, and
persists a byte-offset cursor so it can resume after a restart without
re-fetching (or missing) anything.

This is poll-based, not push-based — the leader has no notion of which
replicas are connected. Simpler and more robust (a replica can restart or
lose its connection at any time and just resumes from its own cursor) at
the cost of up-to-`poll_interval` staleness, which is an acceptable
tradeoff for the scale this project operates at.

Known limitation: a cursor is a byte offset into the leader's log file,
which a leader `compact()` invalidates (compaction rewrites the file from
offset 0). A replica that syncs across a compaction can silently miss or
duplicate records. Not solved here — a real fix needs either disabling
compaction while replicas are attached or a compaction-aware cursor
scheme; out of scope for this pass.
"""
import os
import time

from .client import call
from .store import KVStore


def _cursor_path(db_path):
    return db_path + ".replica_offset"


def load_cursor(db_path):
    path = _cursor_path(db_path)
    if not os.path.exists(path):
        return 0
    with open(path) as f:
        content = f.read().strip()
    return int(content) if content else 0


def save_cursor(db_path, offset):
    path = _cursor_path(db_path)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(str(offset))
    os.replace(tmp_path, path)


def apply_records(store, records):
    """Apply a batch of {"op", "key", "value"} dicts, as returned by a
    leader's sync response, to a local KVStore in order."""
    for record in records:
        op = record["op"]
        key = record["key"]
        if op == "put":
            store.put(key, record.get("value"))
        elif op == "delete":
            if key in store:
                store.delete(key)


def sync_once(store, host, port, cursor):
    """Pull and apply every leader record appended since `cursor`.
    Returns the new cursor (unchanged if there was nothing new)."""
    response = call(host, port, "sync", since=cursor)
    apply_records(store, response["records"])
    return response["offset"]


def run_replica(
    db_path,
    host,
    port,
    poll_interval=1.0,
    fsync="always",
    stop_event=None,
    sleep_fn=time.sleep,
    on_sync=None,
):
    """Continuously pull new records from a leader kvlog server and apply
    them to a local KVStore, until stop_event is set (or forever, if no
    stop_event is given).

    Resumes from db_path's persisted cursor on startup, so a restarted
    replica doesn't need a full resync. `on_sync`, if given, is called
    with the new cursor after each round — lets tests observe progress
    without depending on real wall-clock sleeps.
    """
    store = KVStore(db_path, fsync=fsync)
    cursor = load_cursor(db_path)
    try:
        while stop_event is None or not stop_event.is_set():
            cursor = sync_once(store, host, port, cursor)
            save_cursor(db_path, cursor)
            if on_sync:
                on_sync(cursor)
            sleep_fn(poll_interval)
    finally:
        store.close()
