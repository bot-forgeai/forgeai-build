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


def load_index(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Index.from_dict(data)


def load_or_new_index(path):
    try:
        return load_index(path)
    except FileNotFoundError:
        return Index()
