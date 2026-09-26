"""Tree objects: a snapshot of every tracked path to its blob sha.

One tree object per directory, the same nesting real git uses: a tree
object's content is a sorted list of `kind\tsha\tname` entries, where
an entry is either a `blob` (a file) or another `tree` (a
subdirectory). Because objects are content-addressed, an unmodified
subdirectory across two commits hashes to the exact same tree object
and is stored/transferred only once — the flat one-tree-per-commit
design used before this couldn't share anything below the root.

The public interface (`write_tree`/`read_tree`) still trades in flat
`path -> blob sha` dicts, so every other module keeps working
unchanged; only the on-disk shape changed.
"""
from . import objects as objects_mod


def _nest(index: dict) -> dict:
    """Turn a flat path->sha dict into a nested dict of dicts, leaves
    being blob shas (strings) and directories being nested dicts."""
    root: dict = {}
    for path, sha in index.items():
        parts = path.split("/")
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = sha
    return root


def _write_node(repo_dir: str, node: dict) -> str:
    lines = []
    for name in sorted(node):
        value = node[name]
        if isinstance(value, dict):
            sub_sha = _write_node(repo_dir, value)
            lines.append(f"tree\t{sub_sha}\t{name}")
        else:
            lines.append(f"blob\t{value}\t{name}")
    data = "\n".join(lines).encode()
    return objects_mod.write_object(repo_dir, data, "tree")


def write_tree(repo_dir: str, index: dict) -> str:
    return _write_node(repo_dir, _nest(index))


def _read_entries(repo_dir: str, sha: str) -> list[tuple[str, str, str]]:
    """Parse a tree object into (kind, sha, name) entries."""
    obj_type, data = objects_mod.read_object(repo_dir, sha)
    if obj_type != "tree":
        raise ValueError(f"object {sha} is not a tree (got {obj_type})")
    if not data:
        return []
    entries = []
    for line in data.decode().split("\n"):
        kind, _, rest = line.partition("\t")
        entry_sha, _, name = rest.partition("\t")
        entries.append((kind, entry_sha, name))
    return entries


def read_tree(repo_dir: str, sha: str) -> dict:
    result: dict = {}
    for kind, entry_sha, name in _read_entries(repo_dir, sha):
        if kind == "tree":
            for sub_path, blob_sha in read_tree(repo_dir, entry_sha).items():
                result[f"{name}/{sub_path}"] = blob_sha
        else:
            result[name] = entry_sha
    return result


def collect_tree_shas(repo_dir: str, sha: str) -> set:
    """This tree's own sha plus every subtree sha reachable from it
    (not blobs) — used by remote transfer to copy directory objects,
    not just files, since they're now real objects of their own."""
    collected = {sha}
    for kind, entry_sha, _name in _read_entries(repo_dir, sha):
        if kind == "tree":
            collected.update(collect_tree_shas(repo_dir, entry_sha))
    return collected
