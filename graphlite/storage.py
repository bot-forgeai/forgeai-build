"""Single-JSON-file persistence for a graphlite Graph."""

import json
import os
import tempfile

from .model import Graph


def load(path):
    if not os.path.exists(path):
        return Graph()
    with open(path) as f:
        data = json.load(f)
    return Graph.from_dict(data)


def save(graph, path):
    """Write the whole graph as one atomic operation (temp file + fsync + os.replace)."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".graphlite-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(graph.to_dict(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
