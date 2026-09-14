"""Tree objects: a snapshot of every tracked path to its blob sha.

Real git nests one tree object per directory; vcslite keeps a single
flat tree object per commit (path -> blob sha, sorted), which is
simpler to reason about and is a fine tradeoff at this project's scale.
"""
from . import objects as objects_mod


def write_tree(repo_dir: str, index: dict) -> str:
    lines = [f"{sha}\t{path}" for path, sha in sorted(index.items())]
    data = "\n".join(lines).encode()
    return objects_mod.write_object(repo_dir, data, "tree")


def read_tree(repo_dir: str, sha: str) -> dict:
    obj_type, data = objects_mod.read_object(repo_dir, sha)
    if obj_type != "tree":
        raise ValueError(f"object {sha} is not a tree (got {obj_type})")
    if not data:
        return {}
    result = {}
    for line in data.decode().split("\n"):
        sha_part, _, path = line.partition("\t")
        result[path] = sha_part
    return result
