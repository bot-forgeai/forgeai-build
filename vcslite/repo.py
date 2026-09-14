"""Repository discovery and initialization."""
import json
import os

REPO_DIR_NAME = ".vcslite"


def find_repo_root(start: str = ".") -> str:
    """Walk upward from `start` looking for a .vcslite directory.

    Returns the working-tree root (the directory containing .vcslite),
    not the .vcslite directory itself.
    """
    current = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(current, REPO_DIR_NAME)):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise FileNotFoundError("not a vcslite repository (no .vcslite found)")
        current = parent


def repo_dir(root: str) -> str:
    return os.path.join(root, REPO_DIR_NAME)


def init(path: str = ".") -> str:
    root = os.path.abspath(path)
    vdir = repo_dir(root)
    if os.path.isdir(vdir):
        raise FileExistsError(f"repository already exists at {vdir}")
    os.makedirs(os.path.join(vdir, "objects"))
    os.makedirs(os.path.join(vdir, "refs", "heads"))
    with open(os.path.join(vdir, "HEAD"), "w") as f:
        f.write("ref: refs/heads/main\n")
    with open(os.path.join(vdir, "index.json"), "w") as f:
        f.write("{}")
    return root


def _read_head_raw(root: str) -> str:
    with open(os.path.join(repo_dir(root), "HEAD")) as f:
        return f.read().strip()


def read_head_ref(root: str) -> str:
    """Return the ref path HEAD points at, e.g. 'refs/heads/main'.

    Raises ValueError if HEAD is detached (points directly at a commit).
    """
    line = _read_head_raw(root)
    if line.startswith("ref: "):
        return line[len("ref: "):]
    raise ValueError(f"detached or malformed HEAD: {line!r}")


def current_branch(root: str) -> str | None:
    """The branch name HEAD points at, or None if HEAD is detached."""
    line = _read_head_raw(root)
    if line.startswith("ref: refs/heads/"):
        return line[len("ref: refs/heads/"):]
    return None


def set_head_branch(root: str, name: str) -> None:
    """Point HEAD at a branch (symbolic ref)."""
    with open(os.path.join(repo_dir(root), "HEAD"), "w") as f:
        f.write(f"ref: refs/heads/{name}\n")


def set_head_detached(root: str, sha: str) -> None:
    """Point HEAD directly at a commit, leaving no branch behind it."""
    with open(os.path.join(repo_dir(root), "HEAD"), "w") as f:
        f.write(sha + "\n")


def list_branches(root: str) -> list[str]:
    heads_dir = os.path.join(repo_dir(root), "refs", "heads")
    if not os.path.isdir(heads_dir):
        return []
    return sorted(os.listdir(heads_dir))


def branch_exists(root: str, name: str) -> bool:
    return os.path.isfile(os.path.join(repo_dir(root), "refs", "heads", name))


def read_ref(root: str, ref: str) -> str | None:
    path = os.path.join(repo_dir(root), ref)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return f.read().strip() or None


def write_ref(root: str, ref: str, sha: str) -> None:
    path = os.path.join(repo_dir(root), ref)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(sha + "\n")


def current_commit(root: str) -> str | None:
    line = _read_head_raw(root)
    if line.startswith("ref: "):
        return read_ref(root, line[len("ref: "):])
    return line or None


def _merge_head_path(root: str) -> str:
    return os.path.join(repo_dir(root), "MERGE_HEAD")


def merge_head(root: str) -> str | None:
    """The sha of the other branch's tip mid-merge, or None if not merging."""
    path = _merge_head_path(root)
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return f.read().strip() or None


def set_merge_head(root: str, sha: str) -> None:
    with open(_merge_head_path(root), "w") as f:
        f.write(sha + "\n")


def clear_merge_head(root: str) -> None:
    path = _merge_head_path(root)
    if os.path.isfile(path):
        os.remove(path)


def _merge_conflicts_path(root: str) -> str:
    return os.path.join(repo_dir(root), "MERGE_CONFLICTS")


def merge_conflicts(root: str) -> list[str]:
    path = _merge_conflicts_path(root)
    if not os.path.isfile(path):
        return []
    with open(path) as f:
        return json.load(f)


def set_merge_conflicts(root: str, paths: list[str]) -> None:
    with open(_merge_conflicts_path(root), "w") as f:
        json.dump(paths, f)


def clear_merge_conflicts(root: str) -> None:
    path = _merge_conflicts_path(root)
    if os.path.isfile(path):
        os.remove(path)
