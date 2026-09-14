"""Working-tree scanning and status computation."""
import fnmatch
import os

from . import commit as commit_mod
from . import objects as objects_mod
from . import repo as repo_mod
from . import tree as tree_mod
from .index import read_index

IGNORED_DIRS = {repo_mod.REPO_DIR_NAME, ".git", "__pycache__"}
IGNORE_FILE_NAME = ".vcsliteignore"


def load_ignore_patterns(root: str) -> list[str]:
    """Read .vcsliteignore from the repo root: one glob pattern per line.

    Blank lines and lines starting with '#' are ignored. Returns [] if
    the file doesn't exist.
    """
    path = os.path.join(root, IGNORE_FILE_NAME)
    if not os.path.isfile(path):
        return []
    patterns = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)
    return patterns


def is_ignored(rel_path: str, patterns: list[str]) -> bool:
    """Whether rel_path matches any ignore pattern.

    A pattern matches the whole relative path, or any single path
    component (so "build/" or "build" both ignore a build/ directory
    anywhere in the tree, the way a bare directory name does in
    .gitignore).
    """
    parts = rel_path.split("/")
    for pattern in patterns:
        pat = pattern.rstrip("/")
        if fnmatch.fnmatch(rel_path, pattern) or any(
            fnmatch.fnmatch(part, pat) for part in parts
        ):
            return True
    return False


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


def list_addable_files(root: str) -> list[str]:
    """Every working file not excluded by .vcsliteignore, sorted."""
    patterns = load_ignore_patterns(root)
    return [p for p in list_working_files(root) if not is_ignored(p, patterns)]


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
    patterns = load_ignore_patterns(root)
    on_disk_addable = {p for p in on_disk if not is_ignored(p, patterns)}

    staged = sorted(
        path for path, sha in index.items()
        if committed.get(path) != sha
    )
    untracked = sorted(on_disk_addable - set(index.keys()))
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
