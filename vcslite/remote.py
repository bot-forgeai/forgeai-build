"""Remotes: filesystem-path-based clone/push/fetch/pull between repos.

No networking is involved — a "remote" is just another vcslite repo's
working-tree root reachable on the local filesystem (or a mounted
path). Transfer works the way git's own does: walk the commit/tree/
blob objects reachable from a ref and copy over only the ones the
destination doesn't already have, then move the destination's ref.
"""
import json
import os

from . import commit as commit_mod
from . import merge as merge_mod
from . import objects as objects_mod
from . import repo as repo_mod
from . import tree as tree_mod
from . import worktree as worktree_mod
from .index import write_index

REMOTES_FILE = "remotes.json"


def _remotes_path(root: str) -> str:
    return os.path.join(repo_mod.repo_dir(root), REMOTES_FILE)


def read_remotes(root: str) -> dict:
    path = _remotes_path(root)
    if not os.path.isfile(path):
        return {}
    with open(path) as f:
        return json.load(f)


def write_remotes(root: str, remotes: dict) -> None:
    with open(_remotes_path(root), "w") as f:
        json.dump(remotes, f, indent=2, sort_keys=True)


def add_remote(root: str, name: str, path: str) -> None:
    remotes = read_remotes(root)
    remotes[name] = os.path.abspath(path)
    write_remotes(root, remotes)


def remote_root(root: str, name: str) -> str:
    """The working-tree root of a registered remote, re-resolved fresh
    each time (the remote itself may have moved since it was added, as
    long as the recorded path still finds a repo)."""
    remotes = read_remotes(root)
    if name not in remotes:
        raise KeyError(f"no such remote: {name}")
    return repo_mod.find_repo_root(remotes[name])


def collect_objects(repo_dir: str, sha: str) -> set:
    """Every commit/tree/blob sha reachable from commit `sha`."""
    collected: set = set()
    stack = [sha]
    while stack:
        csha = stack.pop()
        if csha is None or csha in collected:
            continue
        collected.add(csha)
        c = commit_mod.read_commit(repo_dir, csha)
        collected.add(c["tree"])
        collected.update(tree_mod.read_tree(repo_dir, c["tree"]).values())
        stack.extend(c["parents"])
    return collected


def transfer_objects(src_dir: str, dest_dir: str, shas: set) -> int:
    """Copy every sha in `shas` from src_dir to dest_dir that dest_dir
    doesn't already have. Returns how many were actually copied."""
    count = 0
    for sha in shas:
        if not objects_mod.object_exists(dest_dir, sha):
            obj_type, data = objects_mod.read_object(src_dir, sha)
            objects_mod.write_object(dest_dir, data, obj_type)
            count += 1
    return count


def clone(src_path: str, dest_path: str) -> str:
    """Create a new repo at dest_path with every object and branch from
    the repo at src_path, checked out to src's current branch (or its
    first branch alphabetically if HEAD there is detached), and 'origin'
    registered as a remote pointing back at the source.
    """
    src_root = repo_mod.find_repo_root(src_path)
    if os.path.isdir(dest_path) and os.listdir(dest_path):
        raise FileExistsError(f"destination path already exists and is not empty: {dest_path}")

    src_dir = repo_mod.repo_dir(src_root)
    dest_root = repo_mod.init(dest_path)
    dest_dir = repo_mod.repo_dir(dest_root)

    for branch in repo_mod.list_branches(src_root):
        sha = repo_mod.read_ref(src_root, f"refs/heads/{branch}")
        if sha is None:
            continue
        transfer_objects(src_dir, dest_dir, collect_objects(src_dir, sha))
        repo_mod.write_ref(dest_root, f"refs/heads/{branch}", sha)

    add_remote(dest_root, "origin", src_root)

    checkout_branch = repo_mod.current_branch(src_root)
    if checkout_branch is None or not repo_mod.branch_exists(dest_root, checkout_branch):
        branches = repo_mod.list_branches(dest_root)
        checkout_branch = branches[0] if branches else None

    if checkout_branch is not None:
        sha = repo_mod.read_ref(dest_root, f"refs/heads/{checkout_branch}")
        c = commit_mod.read_commit(dest_dir, sha)
        target_tree = tree_mod.read_tree(dest_dir, c["tree"])
        worktree_mod.write_tree_to_worktree(dest_root, dest_dir, target_tree)
        write_index(dest_root, dict(target_tree))
        repo_mod.set_head_branch(dest_root, checkout_branch)

    return dest_root


def push(root: str, remote_name: str, branch: str) -> dict:
    """Copy `branch`'s missing objects to `remote_name` and move its ref
    there. Rejected (ValueError) unless the remote's current tip for
    that branch is an ancestor of the local one (or doesn't exist yet)
    — a fast-forward-only push, the simplest safe policy at this scale.
    """
    rdir = repo_mod.repo_dir(root)
    r_root = remote_root(root, remote_name)
    r_dir = repo_mod.repo_dir(r_root)

    local_sha = repo_mod.read_ref(root, f"refs/heads/{branch}")
    if local_sha is None:
        raise ValueError(f"no such local branch: {branch}")

    remote_sha = repo_mod.read_ref(r_root, f"refs/heads/{branch}")
    if remote_sha is not None and remote_sha != local_sha:
        if remote_sha not in merge_mod.ancestors(rdir, local_sha):
            raise ValueError(
                f"push rejected: {remote_name}/{branch} is not an ancestor of "
                f"local {branch} (fetch/pull first)"
            )

    transferred = transfer_objects(rdir, r_dir, collect_objects(rdir, local_sha))
    repo_mod.write_ref(r_root, f"refs/heads/{branch}", local_sha)
    return {"sha": local_sha, "objects_sent": transferred}


def fetch(root: str, remote_name: str) -> dict:
    """Copy every branch's missing objects from `remote_name` into the
    local object store, recording each one under refs/remotes/<name>/
    <branch> without touching the working tree or local branches."""
    r_root = remote_root(root, remote_name)
    r_dir = repo_mod.repo_dir(r_root)
    rdir = repo_mod.repo_dir(root)

    updated = {}
    total_objects = 0
    for branch in repo_mod.list_branches(r_root):
        sha = repo_mod.read_ref(r_root, f"refs/heads/{branch}")
        if sha is None:
            continue
        total_objects += transfer_objects(r_dir, rdir, collect_objects(r_dir, sha))
        repo_mod.write_ref(root, f"refs/remotes/{remote_name}/{branch}", sha)
        updated[branch] = sha
    return {"branches": updated, "objects_received": total_objects}


def pull(root: str, remote_name: str, branch: str) -> dict:
    """Fetch `remote_name`, then merge its `branch` into the current one."""
    fetch(root, remote_name)
    theirs_sha = repo_mod.read_ref(root, f"refs/remotes/{remote_name}/{branch}")
    if theirs_sha is None:
        raise ValueError(f"no such branch on {remote_name}: {branch}")
    return merge_mod.execute_merge(root, theirs_sha, f"{remote_name}/{branch}")
