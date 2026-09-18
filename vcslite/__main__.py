"""CLI entry point for vcslite."""
import argparse
import difflib
import os
import sys

from . import commit as commit_mod
from . import merge as merge_mod
from . import objects as objects_mod
from . import remote as remote_mod
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
        targets = worktree_mod.list_addable_files(root)

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
    merge_parent = repo_mod.merge_head(root)
    if parent is not None and merge_parent is None:
        parent_tree = commit_mod.read_commit(rdir, parent)["tree"]
        if parent_tree == tree_sha:
            print("error: nothing to commit (tree unchanged)", file=sys.stderr)
            return 1

    parents = [p for p in (parent, merge_parent) if p is not None]
    sha = commit_mod.write_commit(rdir, tree_sha, parents, args.message)
    branch = repo_mod.current_branch(root)
    if branch is not None:
        repo_mod.write_ref(root, f"refs/heads/{branch}", sha)
        label = branch
    else:
        repo_mod.set_head_detached(root, sha)
        label = "detached HEAD"
    if merge_parent is not None:
        repo_mod.clear_merge_head(root)
        repo_mod.clear_merge_conflicts(root)
    print(f"[{label} {sha[:8]}] {args.message}")
    return 0


def cmd_branch(args):
    root = repo_mod.find_repo_root(".")
    if args.name is None:
        current = repo_mod.current_branch(root)
        for name in repo_mod.list_branches(root):
            marker = "*" if name == current else " "
            print(f"{marker} {name}")
        return 0

    if repo_mod.branch_exists(root, args.name):
        print(f"error: branch {args.name!r} already exists", file=sys.stderr)
        return 1

    sha = repo_mod.current_commit(root)
    if sha is None:
        print("error: cannot create a branch before the first commit", file=sys.stderr)
        return 1

    repo_mod.write_ref(root, f"refs/heads/{args.name}", sha)
    print(f"created branch '{args.name}' at {sha[:8]}")
    return 0


def cmd_status(args):
    root = repo_mod.find_repo_root(".")
    branch = repo_mod.current_branch(root)
    if branch is not None:
        print(f"on branch {branch}")
    else:
        sha = repo_mod.current_commit(root)
        print(f"HEAD detached at {sha[:8] if sha else '(no commits)'}")
    merging = repo_mod.merge_head(root)
    conflicts = repo_mod.merge_conflicts(root) if merging is not None else []
    if merging is not None:
        print(f"merging {merging[:8]} — resolve conflicts, add, then commit")
        if conflicts:
            print("conflicted:")
            for p in conflicts:
                print(f"  {p}")

    s = worktree_mod.status(root)
    if conflicts:
        s = {key: [p for p in paths if p not in conflicts] for key, paths in s.items()}
    if not any(s.values()):
        if merging is None:
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
        header = f"commit {sha}"
        if len(c["parents"]) > 1:
            header += f" (merge: {', '.join(p[:8] for p in c['parents'])})"
        print(header)
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

    if args.new_branch:
        if repo_mod.branch_exists(root, args.new_branch):
            print(f"error: branch {args.new_branch!r} already exists", file=sys.stderr)
            return 1
        if args.commit is None:
            target = repo_mod.current_commit(root)
            if target is None:
                print("error: cannot create a branch before the first commit", file=sys.stderr)
                return 1
        else:
            try:
                target = _resolve_commit(root, args.commit)
            except (KeyError, ValueError) as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
        repo_mod.write_ref(root, f"refs/heads/{args.new_branch}", target)
        branch_name = args.new_branch
    elif args.commit is None:
        print("error: checkout requires a branch name or commit", file=sys.stderr)
        return 1
    elif repo_mod.branch_exists(root, args.commit):
        branch_name = args.commit
        target = repo_mod.read_ref(root, f"refs/heads/{branch_name}")
        if target is None:
            print(f"error: branch {branch_name!r} has no commits yet", file=sys.stderr)
            return 1
    else:
        try:
            target = _resolve_commit(root, args.commit)
        except (KeyError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        branch_name = None

    try:
        c = commit_mod.read_commit(rdir, target)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    target_tree = tree_mod.read_tree(rdir, c["tree"])
    worktree_mod.write_tree_to_worktree(root, rdir, target_tree)
    write_index(root, dict(target_tree))

    if branch_name is not None:
        repo_mod.set_head_branch(root, branch_name)
        print(f"switched to branch '{branch_name}' at {target[:8]}")
    else:
        repo_mod.set_head_detached(root, target)
        print(f"checked out {target[:8]} (detached HEAD)")
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


def _print_merge_result(result: dict, label: str, current_branch: str | None = None) -> int:
    status = result["status"]
    if status == "up_to_date":
        print("already up to date")
        return 0
    if status == "fast_forward":
        target = current_branch or "HEAD"
        print(f"fast-forwarded {target} to {result['sha'][:8]}")
        return 0
    if status == "conflict":
        print(f"conflict: {len(result['conflicts'])} file(s) need manual resolution:")
        for p in result["conflicts"]:
            print(f"  {p}")
        print("resolve, then `vcslite add` and `vcslite commit`")
        return 1
    if status == "merged":
        into = f" into {current_branch}" if current_branch else ""
        print(f"merged {label}{into} at {result['sha'][:8]}")
        return 0
    print(f"error: {result['message']}", file=sys.stderr)
    return 1


def cmd_merge(args):
    root = repo_mod.find_repo_root(".")
    rdir = repo_mod.repo_dir(root)

    if args.abort:
        if repo_mod.merge_head(root) is None:
            print("error: no merge in progress", file=sys.stderr)
            return 1
        head_sha = repo_mod.current_commit(root)
        c = commit_mod.read_commit(rdir, head_sha)
        target_tree = tree_mod.read_tree(rdir, c["tree"])
        worktree_mod.write_tree_to_worktree(root, rdir, target_tree)
        write_index(root, dict(target_tree))
        repo_mod.clear_merge_head(root)
        repo_mod.clear_merge_conflicts(root)
        print("merge aborted")
        return 0

    if args.branch is None:
        print("error: merge requires a branch name or commit", file=sys.stderr)
        return 1

    if repo_mod.merge_head(root) is not None:
        print("error: a merge is already in progress (resolve conflicts, then commit)",
              file=sys.stderr)
        return 1

    if repo_mod.branch_exists(root, args.branch):
        theirs_sha = repo_mod.read_ref(root, f"refs/heads/{args.branch}")
        if theirs_sha is None:
            print(f"error: branch {args.branch!r} has no commits yet", file=sys.stderr)
            return 1
    else:
        try:
            theirs_sha = _resolve_commit(root, args.branch)
        except (KeyError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1

    current_branch = repo_mod.current_branch(root)
    result = merge_mod.execute_merge(root, theirs_sha, args.branch)
    return _print_merge_result(result, args.branch, current_branch)


def cmd_clone(args):
    try:
        dest_root = remote_mod.clone(args.src, args.dest)
    except (FileNotFoundError, FileExistsError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"cloned into {dest_root}")
    return 0


def cmd_remote(args):
    root = repo_mod.find_repo_root(".")
    if args.remote_command == "add":
        remote_mod.add_remote(root, args.name, args.path)
        print(f"added remote '{args.name}' -> {os.path.abspath(args.path)}")
        return 0
    remotes = remote_mod.read_remotes(root)
    for name, path in sorted(remotes.items()):
        print(f"{name}\t{path}")
    return 0


def cmd_push(args):
    root = repo_mod.find_repo_root(".")
    branch = args.branch or repo_mod.current_branch(root)
    if branch is None:
        print("error: cannot push from a detached HEAD without naming a branch",
              file=sys.stderr)
        return 1
    try:
        result = remote_mod.push(root, args.remote, branch)
    except (KeyError, ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"pushed {branch} to {args.remote} "
          f"({result['objects_sent']} object(s) sent), now at {result['sha'][:8]}")
    return 0


def cmd_fetch(args):
    root = repo_mod.find_repo_root(".")
    try:
        result = remote_mod.fetch(root, args.remote)
    except (KeyError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    for branch, sha in sorted(result["branches"].items()):
        print(f"  {args.remote}/{branch} -> {sha[:8]}")
    print(f"fetched {result['objects_received']} object(s)")
    return 0


def cmd_pull(args):
    root = repo_mod.find_repo_root(".")
    current_branch = repo_mod.current_branch(root)
    try:
        result = remote_mod.pull(root, args.remote, args.branch)
    except (KeyError, ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return _print_merge_result(result, f"{args.remote}/{args.branch}", current_branch)


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

    p_branch = sub.add_parser("branch", help="list branches, or create one")
    p_branch.add_argument("name", nargs="?", default=None,
                           help="name for a new branch pointing at HEAD")
    p_branch.set_defaults(func=cmd_branch)

    p_checkout = sub.add_parser(
        "checkout", help="switch to a branch, or restore working tree to a commit"
    )
    p_checkout.add_argument("commit", nargs="?", default=None,
                             help="branch name or commit sha")
    p_checkout.add_argument("-b", dest="new_branch", metavar="NAME",
                             help="create NAME as a new branch and switch to it")
    p_checkout.set_defaults(func=cmd_checkout)

    p_diff = sub.add_parser("diff", help="show staged changes vs HEAD")
    p_diff.set_defaults(func=cmd_diff)

    p_merge = sub.add_parser("merge", help="merge a branch into the current one")
    p_merge.add_argument("branch", nargs="?", default=None,
                          help="branch name or commit to merge in")
    p_merge.add_argument("--abort", action="store_true",
                          help="abandon an in-progress conflicted merge")
    p_merge.set_defaults(func=cmd_merge)

    p_clone = sub.add_parser("clone", help="clone a repository into a new directory")
    p_clone.add_argument("src")
    p_clone.add_argument("dest")
    p_clone.set_defaults(func=cmd_clone)

    p_remote = sub.add_parser("remote", help="list or add remotes (paths to other vcslite repos)")
    remote_sub = p_remote.add_subparsers(dest="remote_command")
    p_remote_add = remote_sub.add_parser("add", help="register a remote")
    p_remote_add.add_argument("name")
    p_remote_add.add_argument("path")
    p_remote.set_defaults(func=cmd_remote)

    p_push = sub.add_parser("push", help="push a branch's commits to a remote")
    p_push.add_argument("remote")
    p_push.add_argument("branch", nargs="?", default=None,
                         help="defaults to the current branch")
    p_push.set_defaults(func=cmd_push)

    p_fetch = sub.add_parser("fetch", help="fetch a remote's branches without merging")
    p_fetch.add_argument("remote")
    p_fetch.set_defaults(func=cmd_fetch)

    p_pull = sub.add_parser("pull", help="fetch a remote branch and merge it into the current one")
    p_pull.add_argument("remote")
    p_pull.add_argument("branch")
    p_pull.set_defaults(func=cmd_pull)

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
