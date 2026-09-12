import os

from .log import append_record, iter_records


class KVStore:
    """A key-value store backed by an append-only log file on disk.

    Every put/delete is appended as a record and immediately flushed;
    the in-memory dict is rebuilt by replaying the log from scratch on
    open, so the store recovers correctly after a crash (any trailing
    incomplete record is simply dropped by iter_records).
    """

    def __init__(self, path):
        self.path = path
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
        append_record(self._file, "put", key, value)
        self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    def delete(self, key):
        if key not in self._data:
            return False
        append_record(self._file, "delete", key)
        del self._data[key]
        return True

    def keys(self):
        return sorted(self._data.keys())

    def items(self):
        return sorted(self._data.items())

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data

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
                append_record(tmp, "put", key, value)
        os.replace(tmp_path, self.path)
        self._file = open(self.path, "ab")

    def close(self):
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
