"""Repository discovery and initialization."""
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


def read_head_ref(root: str) -> str:
    """Return the ref path HEAD points at, e.g. 'refs/heads/main'."""
    with open(os.path.join(repo_dir(root), "HEAD")) as f:
        line = f.read().strip()
    if line.startswith("ref: "):
        return line[len("ref: "):]
    raise ValueError(f"detached or malformed HEAD: {line!r}")


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
    ref = read_head_ref(root)
    return read_ref(root, ref)
