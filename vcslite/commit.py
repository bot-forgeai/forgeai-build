"""Commit objects: a tree snapshot plus parent link, message, timestamp."""
import time

from . import objects as objects_mod


def write_commit(repo_dir: str, tree_sha: str, parents: str | list[str] | None,
                  message: str, timestamp: float | None = None) -> str:
    """Write a commit object. `parents` may be a single sha, a list of
    shas (a merge commit has two), or None/empty for the first commit.
    """
    if timestamp is None:
        timestamp = time.time()
    if parents is None:
        parents = []
    elif isinstance(parents, str):
        parents = [parents]
    lines = [f"tree {tree_sha}"]
    for parent in parents:
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
    result: dict = {"parents": [], "message": message}
    for line in header.split("\n"):
        key, _, value = line.partition(" ")
        if key == "tree":
            result["tree"] = value
        elif key == "parent":
            result["parents"].append(value)
        elif key == "timestamp":
            result["timestamp"] = float(value)
    result["parent"] = result["parents"][0] if result["parents"] else None
    return result
