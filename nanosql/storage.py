"""Single-JSON-file persistence for a nanosql Database."""

import json
import os
import tempfile

from .engine import Database


def load(path):
    if not os.path.exists(path):
        return Database()
    with open(path) as f:
        data = json.load(f)
    return Database.from_dict(data)


def save(db, path):
    """Write the whole database as one atomic operation.

    A plain ``open(path, "w")`` write can leave a half-written, corrupt
    JSON file behind if the process is interrupted mid-write. Writing to a
    temp file in the same directory, fsyncing it, then os.replace-ing it
    into place means a crash at any point before the replace leaves the
    original file untouched, and os.replace itself is atomic — there is no
    window where `path` contains a partial write.
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".nanosql-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(db.to_dict(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
