"""Commit objects: a tree snapshot plus parent link, message, timestamp."""
import time

from . import objects as objects_mod


def write_commit(repo_dir: str, tree_sha: str, parent: str | None,
                  message: str, timestamp: float | None = None) -> str:
    if timestamp is None:
        timestamp = time.time()
    lines = [f"tree {tree_sha}"]
    if parent:
        lines.append(f"parent {parent}")
    lines.append(f"timestamp {timestamp}")
    lines.append("")
    lines.append(message)
    data = "\n".join(lines).encode()
    return objects_mod.write_object(repo_dir, data, "commit")


def read_commit(repo_dir: str, sha: str) -> dict:
    obj_type, data = objects_mod.read_object(repo_dir, sha)
    if obj_type != "commit":
        raise ValueError(f"object {sha} is not a commit (got {obj_type})")
    text = data.decode()
    header, _, message = text.partition("\n\n")
    result: dict = {"parent": None, "message": message}
    for line in header.split("\n"):
        key, _, value = line.partition(" ")
        if key == "tree":
            result["tree"] = value
        elif key == "parent":
            result["parent"] = value
        elif key == "timestamp":
            result["timestamp"] = float(value)
    return result
