"""Single-JSON-file persistence for a nanosql Database."""

import json
import os

from .engine import Database


def load(path):
    if not os.path.exists(path):
        return Database()
    with open(path) as f:
        data = json.load(f)
    return Database.from_dict(data)


def save(db, path):
    with open(path, "w") as f:
        json.dump(db.to_dict(), f, indent=2)
