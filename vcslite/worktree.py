"""Working-tree scanning and status computation."""
import os

from . import commit as commit_mod
from . import objects as objects_mod
from . import repo as repo_mod
from . import tree as tree_mod
from .index import read_index

IGNORED_DIRS = {repo_mod.REPO_DIR_NAME, ".git", "__pycache__"}


def list_working_files(root: str) -> list[str]:
    """Return every tracked-eligible file path, relative to root, sorted."""
    paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            paths.append(rel.replace(os.sep, "/"))
    return sorted(paths)


def hash_file(root: str, rel_path: str) -> bytes:
    with open(os.path.join(root, rel_path), "rb") as f:
        return f.read()


def head_tree(root: str) -> dict:
    """The tree of the current HEAD commit, or {} if there is none yet."""
    head_sha = repo_mod.current_commit(root)
    if head_sha is None:
        return {}
    rdir = repo_mod.repo_dir(root)
    c = commit_mod.read_commit(rdir, head_sha)
    return tree_mod.read_tree(rdir, c["tree"])


def status(root: str) -> dict:
    """Classify every path into staged / modified / untracked / deleted.

    - staged: in the index, differing from HEAD's tree (new or changed)
    - modified: on disk, differs from what's staged in the index
    - untracked: on disk, not in the index at all
    - deleted: in the index, missing from disk
    """
    rdir = repo_mod.repo_dir(root)
    index = read_index(root)
    committed = head_tree(root)
    on_disk = set(list_working_files(root))

    staged = sorted(
        path for path, sha in index.items()
        if committed.get(path) != sha
    )
    untracked = sorted(on_disk - set(index.keys()))
    deleted = sorted(set(index.keys()) - on_disk)

    modified = []
    for path in sorted(set(index.keys()) & on_disk):
        data = hash_file(root, path)
        if objects_mod.hash_object(data, "blob") != index[path]:
            modified.append(path)

    return {
        "staged": staged,
        "modified": modified,
        "untracked": untracked,
        "deleted": deleted,
    }
