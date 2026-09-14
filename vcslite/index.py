"""The staging area: a JSON map of repo-relative path -> blob sha."""
import json
import os

from . import repo as repo_mod

INDEX_FILE = "index.json"


def _index_path(root: str) -> str:
    return os.path.join(repo_mod.repo_dir(root), INDEX_FILE)


def read_index(root: str) -> dict:
    path = _index_path(root)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def write_index(root: str, index: dict) -> None:
    with open(_index_path(root), "w") as f:
        json.dump(index, f, indent=2, sort_keys=True)
