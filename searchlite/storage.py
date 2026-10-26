import json
import os

from searchlite.index import Index


def save_index(index, path):
    # write-then-rename so a concurrent search (or a crash) never sees a half-written index
    tmp = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(index.to_dict(), f)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


class IndexCorruptError(Exception):
    """The index file exists but isn't a readable searchlite index."""


def load_index(path):
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except (ValueError, UnicodeDecodeError) as e:
            raise IndexCorruptError(f"{path}: not valid JSON ({e})") from e
    try:
        return Index.from_dict(data)
    except (AttributeError, TypeError, ValueError) as e:
        raise IndexCorruptError(f"{path}: unexpected structure ({e})") from e


def load_or_new_index(path, rebuild=False):
    """Load the index, or an empty one if the file is missing.

    With rebuild=True a corrupt file is renamed to PATH.corrupt (kept for
    inspection) and an empty index is returned instead of raising.
    """
    try:
        return load_index(path)
    except FileNotFoundError:
        return Index()
    except IndexCorruptError:
        if not rebuild:
            raise
        os.replace(path, f"{path}.corrupt")
        return Index()
