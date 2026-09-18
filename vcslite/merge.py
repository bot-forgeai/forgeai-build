"""Three-way branch merging.

Fast-forwards when the current branch is a plain ancestor of the
target; otherwise merges the two trees path-by-path against their
common ancestor, and falls back to git-style conflict markers in the
working tree for any path both sides changed differently.
"""
import os
from collections import deque

from . import commit as commit_mod
from . import objects as objects_mod
from . import repo as repo_mod
from . import tree as tree_mod
from . import worktree as worktree_mod
from .index import write_index


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


def execute_merge(root: str, theirs_sha: str, label: str) -> dict:
    """Merge `theirs_sha` into the current branch's HEAD, mutating repo
    state (refs, working tree, index, MERGE_HEAD) as a side effect.

    Shared by the `merge` CLI command and `pull` (fetch + merge), so
    both go through one implementation. Returns a dict describing the
    outcome:
      {"status": "up_to_date"}
      {"status": "fast_forward", "sha": sha}
      {"status": "conflict", "conflicts": [...]}
      {"status": "merged", "sha": sha}
      {"status": "error", "message": ...}
    """
    rdir = repo_mod.repo_dir(root)
    current_branch = repo_mod.current_branch(root)
    if current_branch is None:
        return {"status": "error", "message": "cannot merge while HEAD is detached"}

    ours_sha = repo_mod.current_commit(root)
    if ours_sha is None:
        return {"status": "error", "message": "cannot merge before the first commit"}

    if theirs_sha == ours_sha:
        return {"status": "up_to_date"}

    base_sha = merge_base(rdir, ours_sha, theirs_sha)

    if base_sha == theirs_sha:
        return {"status": "up_to_date"}

    if base_sha == ours_sha:
        c = commit_mod.read_commit(rdir, theirs_sha)
        target_tree = tree_mod.read_tree(rdir, c["tree"])
        worktree_mod.write_tree_to_worktree(root, rdir, target_tree)
        write_index(root, dict(target_tree))
        repo_mod.write_ref(root, f"refs/heads/{current_branch}", theirs_sha)
        return {"status": "fast_forward", "sha": theirs_sha}

    base_tree = (tree_mod.read_tree(rdir, commit_mod.read_commit(rdir, base_sha)["tree"])
                 if base_sha else {})
    ours_tree = tree_mod.read_tree(rdir, commit_mod.read_commit(rdir, ours_sha)["tree"])
    theirs_tree = tree_mod.read_tree(rdir, commit_mod.read_commit(rdir, theirs_sha)["tree"])

    merged, conflicts = merge_trees(base_tree, ours_tree, theirs_tree)

    worktree_content = {path: objects_mod.read_object(rdir, sha)[1]
                         for path, sha in merged.items()}
    for path in conflicts:
        worktree_content[path] = conflict_markers(
            rdir, ours_tree.get(path), theirs_tree.get(path), label
        )

    current_files = set(worktree_mod.list_working_files(root))
    for path in current_files - set(worktree_content.keys()):
        os.remove(os.path.join(root, path))
    for path, data in worktree_content.items():
        abs_path = os.path.join(root, path)
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(data)

    write_index(root, dict(merged))

    if conflicts:
        repo_mod.set_merge_head(root, theirs_sha)
        repo_mod.set_merge_conflicts(root, conflicts)
        return {"status": "conflict", "conflicts": conflicts}

    sha = commit_mod.write_commit(rdir, tree_mod.write_tree(rdir, merged),
                                   [ours_sha, theirs_sha],
                                   f"merge {label} into {current_branch}")
    repo_mod.write_ref(root, f"refs/heads/{current_branch}", sha)
    return {"status": "merged", "sha": sha}
