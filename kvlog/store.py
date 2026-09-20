import os

from .log import append_record, iter_records


class KVStore:
    """A key-value store backed by an append-only log file on disk.

    Every put/delete is appended as a record and immediately flushed;
    the in-memory dict is rebuilt by replaying the log from scratch on
    open, so the store recovers correctly after a crash (any trailing
    incomplete record is simply dropped by iter_records).
    """

    def __init__(self, path, fsync="always"):
        if fsync not in ("always", "never"):
            raise ValueError(f"fsync must be 'always' or 'never', got {fsync!r}")
        self.path = path
        self._fsync = fsync == "always"
        self._data = {}
        self._replay()
        self._file = open(self.path, "ab")

    def _replay(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, "rb") as f:
            for op, key, value in iter_records(f):
                if op == "put":
                    self._data[key] = value
                elif op == "delete":
                    self._data.pop(key, None)

    def put(self, key, value):
        append_record(self._file, "put", key, value, fsync=self._fsync)
        self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    def delete(self, key):
        if key not in self._data:
            return False
        append_record(self._file, "delete", key, fsync=self._fsync)
        del self._data[key]
        return True

    def keys(self):
        return sorted(self._data.keys())

    def items(self):
        return sorted(self._data.items())

    def prefix(self, prefix):
        """Return sorted (key, value) pairs whose key starts with prefix."""
        return [(k, v) for k, v in self.items() if k.startswith(prefix)]

    def range(self, start=None, end=None):
        """Return sorted (key, value) pairs with start <= key <= end.

        Either bound may be omitted (None) to leave that side unbounded.
        """
        return [
            (k, v)
            for k, v in self.items()
            if (start is None or k >= start) and (end is None or k <= end)
        ]

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data

    def offset(self):
        """Current size of the log file in bytes — a cursor a replica can
        later pass back to records_since() to resume from exactly here."""
        self._file.flush()
        return os.path.getsize(self.path) if os.path.exists(self.path) else 0

    def records_since(self, offset):
        """Return (records, new_offset): every record appended after byte
        position `offset` in the log file, as a list of
        {"op", "key", "value"} dicts, plus the file's current size.

        Used for replication — a replica passes back its own cursor as
        `offset` to fetch only what it hasn't already applied. A cursor
        from before a compact() is not valid (the byte layout changes);
        callers replicating across a compaction need a fresh full sync
        from offset 0.
        """
        new_offset = self.offset()
        records = []
        if offset < new_offset:
            with open(self.path, "rb") as f:
                f.seek(offset)
                for op, key, value in iter_records(f):
                    records.append({"op": op, "key": key, "value": value})
        return records, new_offset

    def compact(self):
        """Rewrite the log with exactly one put per live key, dropping all
        deleted/overwritten history. Written to a temp file and swapped in
        with os.replace so a crash mid-compaction never leaves a partial
        file at the real path.
        """
        self._file.close()
        tmp_path = self.path + ".compact.tmp"
        with open(tmp_path, "ab") as tmp:
            for key, value in self.items():
                append_record(tmp, "put", key, value, fsync=self._fsync)
        os.replace(tmp_path, self.path)
        self._file = open(self.path, "ab")

    def close(self):
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
