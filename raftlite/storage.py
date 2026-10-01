"""Durable storage for the three pieces of Raft state the paper requires a
node to persist before it may respond to an RPC: currentTerm, votedFor, and
the log itself. Everything else (commit_index, last_applied, role, the
applied KV store) is safe to lose on restart -- it's either re-derivable by
replaying the log, or will be re-driven by the cluster's next heartbeat.

Kept separate from RaftNode on purpose: RaftNode stays pure/I/O-free (see its
own docstring), so a RaftServer is responsible for calling save_state() after
each state-changing node call and load_state() once at startup.
"""
import json
import os

from raftlite.node import LogEntry


def save_state(path, current_term, voted_for, log_entries):
    """Atomically overwrite path with the given state. A crash mid-write
    leaves either the old file or the new one intact, never a half-written
    one, via write-to-temp + fsync + os.replace (the same pattern nanosql's
    storage.py uses)."""
    data = {
        "current_term": current_term,
        "voted_for": voted_for,
        "log": [e.to_dict() for e in log_entries],
    }
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def load_state(path):
    """Returns (current_term, voted_for, log_entries), or None if no state
    has been persisted at this path yet (a brand-new node)."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    entries = [LogEntry.from_dict(d) for d in data["log"]]
    return data["current_term"], data["voted_for"], entries
