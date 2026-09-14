import json

from searchlite.index import Index


def save_index(index, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index.to_dict(), f)


def load_index(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Index.from_dict(data)


def load_or_new_index(path):
    try:
        return load_index(path)
    except FileNotFoundError:
        return Index()
