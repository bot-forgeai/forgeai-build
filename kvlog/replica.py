"""Leader/replica log shipping: a replica polls a leader's `sync` op for
records it hasn't applied yet, applies them to its own local KVStore, and
persists a byte-offset cursor so it can resume after a restart without
re-fetching (or missing) anything.

This is poll-based, not push-based — the leader has no notion of which
replicas are connected. Simpler and more robust (a replica can restart or
lose its connection at any time and just resumes from its own cursor) at
the cost of up-to-`poll_interval` staleness, which is an acceptable
tradeoff for the scale this project operates at.

A cursor is a byte offset into the leader's log file, which a leader
`compact()` invalidates (compaction rewrites the file from offset 0). To
stay correct across a compaction, the leader also tracks a generation
counter (KVStore.generation, bumped on every compact()) and reports it in
every sync response. A replica persists the last generation it saw
alongside its cursor; if the leader's generation has moved on, the
replica's local state may include keys the compacted log no longer
represents at all, so it clears its own store and does a fresh full sync
from offset 0 before applying anything further.
"""
import os
import time

from .client import call
from .store import KVStore


def _cursor_path(db_path):
    return db_path + ".replica_offset"


def load_cursor(db_path):
    """Return (offset, generation). generation is None for a cursor file
    written before generation tracking existed (or no file at all) — the
    next sync then trusts whatever the leader reports without clearing
    the store, since we have no earlier generation to compare against."""
    path = _cursor_path(db_path)
    if not os.path.exists(path):
        return 0, None
    with open(path) as f:
        content = f.read().strip()
    if not content:
        return 0, None
    parts = content.split()
    offset = int(parts[0])
    generation = int(parts[1]) if len(parts) > 1 else None
    return offset, generation


def save_cursor(db_path, offset, generation):
    path = _cursor_path(db_path)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(f"{offset} {generation}")
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


def sync_once(store, host, port, cursor, generation):
    """Pull and apply every leader record appended since `cursor`.
    Returns (new_cursor, new_generation).

    If the leader's generation has moved on since our last sync (it ran
    compact()), `cursor` is no longer meaningful against the rewritten
    log — clear the local store and do a fresh full sync from offset 0
    instead of applying the (potentially bogus) diff we just fetched.
    """
    response = call(host, port, "sync", since=cursor)
    if generation is not None and response["generation"] != generation:
        store.clear()
        response = call(host, port, "sync", since=0)
    apply_records(store, response["records"])
    return response["offset"], response["generation"]


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
    cursor, generation = load_cursor(db_path)
    try:
        while stop_event is None or not stop_event.is_set():
            cursor, generation = sync_once(store, host, port, cursor, generation)
            save_cursor(db_path, cursor, generation)
            if on_sync:
                on_sync(cursor)
            sleep_fn(poll_interval)
    finally:
        store.close()
