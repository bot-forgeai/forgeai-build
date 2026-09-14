"""CLI entry point for vcslite."""
import argparse
import difflib
import os
import sys

from . import commit as commit_mod
from . import objects as objects_mod
from . import repo as repo_mod
from . import tree as tree_mod
from . import worktree as worktree_mod
from .index import read_index, write_index


def cmd_init(args):
    try:
        root = repo_mod.init(args.path)
    except FileExistsError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"initialized empty vcslite repository in {repo_mod.repo_dir(root)}")
    return 0


def cmd_add(args):
    root = repo_mod.find_repo_root(".")
    rdir = repo_mod.repo_dir(root)
    index = read_index(root)

    targets = args.paths
    if targets == ["."]:
        targets = worktree_mod.list_working_files(root)

    added = 0
    for rel in targets:
        abs_path = os.path.join(root, rel)
        if not os.path.isfile(abs_path):
            print(f"error: no such file: {rel}", file=sys.stderr)
            return 1
        data = worktree_mod.hash_file(root, rel)
        sha = objects_mod.write_object(rdir, data, "blob")
        index[rel] = sha
        added += 1

    write_index(root, index)
    print(f"staged {added} file(s)")
    return 0


def cmd_commit(args):
    root = repo_mod.find_repo_root(".")
    rdir = repo_mod.repo_dir(root)
    index = read_index(root)
    if not index:
        print("error: nothing staged to commit", file=sys.stderr)
        return 1

    tree_sha = tree_mod.write_tree(rdir, index)
    parent = repo_mod.current_commit(root)
    if parent is not None:
        parent_tree = commit_mod.read_commit(rdir, parent)["tree"]
        if parent_tree == tree_sha:
            print("error: nothing to commit (tree unchanged)", file=sys.stderr)
            return 1

    sha = commit_mod.write_commit(rdir, tree_sha, parent, args.message)
    ref = repo_mod.read_head_ref(root)
    repo_mod.write_ref(root, ref, sha)
    print(f"[{ref.split('/')[-1]} {sha[:8]}] {args.message}")
    return 0


def cmd_status(args):
    root = repo_mod.find_repo_root(".")
    s = worktree_mod.status(root)
    if not any(s.values()):
        print("nothing to commit, working tree clean")
        return 0
    if s["staged"]:
        print("staged for commit:")
        for p in s["staged"]:
            print(f"  {p}")
    if s["modified"]:
        print("modified, not staged:")
        for p in s["modified"]:
            print(f"  {p}")
    if s["deleted"]:
        print("deleted, not staged:")
        for p in s["deleted"]:
            print(f"  {p}")
    if s["untracked"]:
        print("untracked:")
        for p in s["untracked"]:
            print(f"  {p}")
    return 0


def cmd_log(args):
    root = repo_mod.find_repo_root(".")
    rdir = repo_mod.repo_dir(root)
    sha = repo_mod.current_commit(root)
    if sha is None:
        print("no commits yet")
        return 0
    while sha:
        c = commit_mod.read_commit(rdir, sha)
        print(f"commit {sha}")
        print(f"    {c['message']}")
        sha = c["parent"]
    return 0


def _resolve_commit(root: str, prefix: str) -> str:
    rdir = repo_mod.repo_dir(root)
    if len(prefix) >= 4:
        subdir, rest = prefix[:2], prefix[2:]
        objdir = os.path.join(rdir, "objects", subdir)
        if os.path.isdir(objdir):
            matches = [subdir + name for name in os.listdir(objdir)
                       if name.startswith(rest)]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValueError(f"ambiguous commit prefix: {prefix}")
    if objects_mod.object_exists(rdir, prefix):
        return prefix
    raise KeyError(f"no such commit: {prefix}")


def cmd_checkout(args):
    root = repo_mod.find_repo_root(".")
    rdir = repo_mod.repo_dir(root)
    try:
        sha = _resolve_commit(root, args.commit)
        c = commit_mod.read_commit(rdir, sha)
    except (KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    target_tree = tree_mod.read_tree(rdir, c["tree"])
    current_files = set(worktree_mod.list_working_files(root))

    for path in current_files - set(target_tree.keys()):
        os.remove(os.path.join(root, path))

    for path, blob_sha in target_tree.items():
        _, data = objects_mod.read_object(rdir, blob_sha)
        abs_path = os.path.join(root, path)
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(data)

    write_index(root, dict(target_tree))
    ref = repo_mod.read_head_ref(root)
    repo_mod.write_ref(root, ref, sha)
    print(f"checked out {sha[:8]}")
    return 0


def cmd_diff(args):
    root = repo_mod.find_repo_root(".")
    committed = worktree_mod.head_tree(root)
    index = read_index(root)
    changed = False
    for path in sorted(set(index.keys()) | set(committed.keys())):
        old_sha = committed.get(path)
        new_sha = index.get(path)
        if old_sha == new_sha:
            continue
        changed = True
        rdir = repo_mod.repo_dir(root)
        old_text = objects_mod.read_object(rdir, old_sha)[1].decode(errors="replace").splitlines(keepends=True) if old_sha else []
        new_text = objects_mod.read_object(rdir, new_sha)[1].decode(errors="replace").splitlines(keepends=True) if new_sha else []
        diff_lines = difflib.unified_diff(
            old_text, new_text, fromfile=f"a/{path}", tofile=f"b/{path}"
        )
        sys.stdout.writelines(diff_lines)
    if not changed:
        print("no staged changes")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="vcslite")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create a new repository")
    p_init.add_argument("path", nargs="?", default=".")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="stage file(s)")
    p_add.add_argument("paths", nargs="+", help="file paths, or '.' for everything")
    p_add.set_defaults(func=cmd_add)

    p_commit = sub.add_parser("commit", help="commit staged changes")
    p_commit.add_argument("-m", "--message", required=True)
    p_commit.set_defaults(func=cmd_commit)

    p_status = sub.add_parser("status", help="show staged/modified/untracked files")
    p_status.set_defaults(func=cmd_status)

    p_log = sub.add_parser("log", help="show commit history")
    p_log.set_defaults(func=cmd_log)

    p_checkout = sub.add_parser("checkout", help="restore working tree to a commit")
    p_checkout.add_argument("commit")
    p_checkout.set_defaults(func=cmd_checkout)

    p_diff = sub.add_parser("diff", help="show staged changes vs HEAD")
    p_diff.set_defaults(func=cmd_diff)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args) or 0
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
