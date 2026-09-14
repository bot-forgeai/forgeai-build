"""Three-way branch merging.

Fast-forwards when the current branch is a plain ancestor of the
target; otherwise merges the two trees path-by-path against their
common ancestor, and falls back to git-style conflict markers in the
working tree for any path both sides changed differently.
"""
from collections import deque

from . import commit as commit_mod
from . import objects as objects_mod


def ancestors(repo_dir: str, sha: str | None) -> set[str]:
    """Every commit reachable from `sha`, following all parents."""
    seen: set[str] = set()
    stack = [sha]
    while stack:
        s = stack.pop()
        if s is None or s in seen:
            continue
        seen.add(s)
        c = commit_mod.read_commit(repo_dir, s)
        stack.extend(c["parents"])
    return seen


def merge_base(repo_dir: str, a: str | None, b: str | None) -> str | None:
    """A commit reachable from both `a` and `b`, nearest to `a`.

    Not guaranteed to be the unique lowest common ancestor in a complex
    multi-merge graph, but correct and sufficient at this project's scale.
    """
    if a is None or b is None:
        return None
    b_ancestors = ancestors(repo_dir, b)
    seen: set[str] = set()
    queue = deque([a])
    while queue:
        s = queue.popleft()
        if s is None or s in seen:
            continue
        seen.add(s)
        if s in b_ancestors:
            return s
        c = commit_mod.read_commit(repo_dir, s)
        queue.extend(c["parents"])
    return None


def merge_trees(base_tree: dict, ours_tree: dict, theirs_tree: dict) -> tuple[dict, list[str]]:
    """3-way merge of path -> blob-sha maps.

    Returns (merged, conflicts): `merged` holds every cleanly-resolved
    path (a path deleted on both/one unchanged side is simply absent),
    `conflicts` lists paths both sides changed differently from the base.
    """
    paths = set(base_tree) | set(ours_tree) | set(theirs_tree)
    merged: dict = {}
    conflicts: list[str] = []
    for path in sorted(paths):
        base_sha = base_tree.get(path)
        ours_sha = ours_tree.get(path)
        theirs_sha = theirs_tree.get(path)
        if ours_sha == theirs_sha:
            if ours_sha is not None:
                merged[path] = ours_sha
        elif ours_sha == base_sha:
            if theirs_sha is not None:
                merged[path] = theirs_sha
        elif theirs_sha == base_sha:
            if ours_sha is not None:
                merged[path] = ours_sha
        else:
            conflicts.append(path)
    return merged, conflicts


def conflict_markers(repo_dir: str, ours_sha: str | None, theirs_sha: str | None,
                      branch_label: str) -> bytes:
    """Build a git-style conflicted file: both sides' full content."""
    def text(sha):
        if sha is None:
            return ""
        content = objects_mod.read_object(repo_dir, sha)[1].decode(errors="replace")
        if content and not content.endswith("\n"):
            content += "\n"
        return content

    body = f"<<<<<<< HEAD\n{text(ours_sha)}=======\n{text(theirs_sha)}>>>>>>> {branch_label}\n"
    return body.encode()
