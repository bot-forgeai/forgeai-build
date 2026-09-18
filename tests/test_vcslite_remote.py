import os

import pytest

from vcslite import remote as remote_mod
from vcslite import repo as repo_mod
from vcslite.__main__ import main


def write(path, content):
    with open(path, "w") as f:
        f.write(content)


def init_repo(root, monkeypatch):
    monkeypatch.chdir(root)
    main(["init"])
    write("a.txt", "hello")
    main(["add", "a.txt"])
    main(["commit", "-m", "first commit"])


def test_clone_copies_objects_and_checks_out(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    init_repo(a, monkeypatch)

    b = tmp_path / "b"
    dest_root = remote_mod.clone(str(a), str(b))

    assert dest_root == str(b)
    assert (b / "a.txt").read_text() == "hello"
    assert repo_mod.current_branch(str(b)) == "main"
    assert repo_mod.read_ref(str(b), "refs/heads/main") == repo_mod.read_ref(str(a), "refs/heads/main")
    remotes = remote_mod.read_remotes(str(b))
    assert remotes["origin"] == str(a)


def test_clone_into_nonempty_dir_errors(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    init_repo(a, monkeypatch)

    b = tmp_path / "b"
    b.mkdir()
    write(b / "existing.txt", "already here")

    with pytest.raises(FileExistsError):
        remote_mod.clone(str(a), str(b))


def test_push_fast_forward(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    init_repo(a, monkeypatch)

    b = tmp_path / "b"
    remote_mod.clone(str(a), str(b))

    monkeypatch.chdir(b)
    write("b_only.txt", "new in b")
    main(["add", "b_only.txt"])
    main(["commit", "-m", "second commit"])
    remote_mod.add_remote(str(b), "origin_check", str(a))  # sanity: origin already added by clone

    result = remote_mod.push(str(b), "origin", "main")
    assert result["objects_sent"] > 0
    assert repo_mod.read_ref(str(a), "refs/heads/main") == result["sha"]


def test_push_rejects_non_fast_forward(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    init_repo(a, monkeypatch)

    b = tmp_path / "b"
    remote_mod.clone(str(a), str(b))

    # Diverge: commit separately in both a and b.
    monkeypatch.chdir(a)
    write("a_only.txt", "new in a")
    main(["add", "a_only.txt"])
    main(["commit", "-m", "a moves on"])

    monkeypatch.chdir(b)
    write("b_only.txt", "new in b")
    main(["add", "b_only.txt"])
    main(["commit", "-m", "b moves on"])

    with pytest.raises(ValueError, match="rejected"):
        remote_mod.push(str(b), "origin", "main")


def test_fetch_updates_remote_tracking_ref_without_touching_worktree(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    init_repo(a, monkeypatch)

    b = tmp_path / "b"
    remote_mod.clone(str(a), str(b))

    monkeypatch.chdir(a)
    write("a_only.txt", "new in a")
    main(["add", "a_only.txt"])
    main(["commit", "-m", "a moves on"])

    result = remote_mod.fetch(str(b), "origin")
    assert result["objects_received"] > 0
    assert repo_mod.read_ref(str(b), "refs/remotes/origin/main") == repo_mod.read_ref(str(a), "refs/heads/main")
    # working tree in b untouched by fetch alone
    assert not (b / "a_only.txt").exists()


def test_pull_merges_nonconflicting_changes(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    init_repo(a, monkeypatch)

    b = tmp_path / "b"
    remote_mod.clone(str(a), str(b))

    monkeypatch.chdir(a)
    write("a_only.txt", "new in a")
    main(["add", "a_only.txt"])
    main(["commit", "-m", "a moves on"])

    monkeypatch.chdir(b)
    write("b_only.txt", "new in b")
    main(["add", "b_only.txt"])
    main(["commit", "-m", "b moves on"])

    result = remote_mod.pull(str(b), "origin", "main")
    assert result["status"] == "merged"
    assert (b / "a_only.txt").read_text() == "new in a"
    assert (b / "b_only.txt").read_text() == "new in b"


def test_pull_fast_forward_when_local_unchanged(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    init_repo(a, monkeypatch)

    b = tmp_path / "b"
    remote_mod.clone(str(a), str(b))

    monkeypatch.chdir(a)
    write("a_only.txt", "new in a")
    main(["add", "a_only.txt"])
    main(["commit", "-m", "a moves on"])

    result = remote_mod.pull(str(b), "origin", "main")
    assert result["status"] == "fast_forward"
    assert (b / "a_only.txt").read_text() == "new in a"


def test_push_unknown_remote_errors(tmp_path, monkeypatch):
    a = tmp_path / "a"
    a.mkdir()
    init_repo(a, monkeypatch)
    with pytest.raises(KeyError):
        remote_mod.push(str(a), "nope", "main")


# --- CLI-level tests ---

def test_cli_clone_and_remote_list(tmp_path, monkeypatch, capsys):
    a = tmp_path / "a"
    a.mkdir()
    init_repo(a, monkeypatch)

    b = tmp_path / "b"
    capsys.readouterr()
    assert main(["clone", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "cloned into" in out

    monkeypatch.chdir(b)
    capsys.readouterr()
    main(["remote"])
    out = capsys.readouterr().out
    assert "origin" in out
    assert str(a) in out


def test_cli_push_pull_roundtrip(tmp_path, monkeypatch, capsys):
    a = tmp_path / "a"
    a.mkdir()
    init_repo(a, monkeypatch)

    b = tmp_path / "b"
    main(["clone", str(a), str(b)])

    monkeypatch.chdir(b)
    write("b_only.txt", "new in b")
    main(["add", "b_only.txt"])
    main(["commit", "-m", "second commit"])
    capsys.readouterr()
    assert main(["push", "origin", "main"]) == 0
    out = capsys.readouterr().out
    assert "pushed main to origin" in out

    # `push` already moved a's ref directly (it writes into the remote's
    # ref file), so `a`'s branch already has the content, though push
    # never touches the remote's own worktree/index (like pushing into a
    # non-bare git repo) — `pull` here is a no-op, not a new merge.
    monkeypatch.chdir(a)
    remote_mod.add_remote(str(a), "origin", str(b))
    capsys.readouterr()
    assert main(["pull", "origin", "main"]) == 0
    out = capsys.readouterr().out
    assert "already up to date" in out
    assert repo_mod.read_ref(str(a), "refs/heads/main") == repo_mod.read_ref(str(b), "refs/heads/main")


def test_cli_fetch_reports_branches(tmp_path, monkeypatch, capsys):
    a = tmp_path / "a"
    a.mkdir()
    init_repo(a, monkeypatch)
    b = tmp_path / "b"
    main(["clone", str(a), str(b)])

    monkeypatch.chdir(a)
    write("a_only.txt", "x")
    main(["add", "a_only.txt"])
    main(["commit", "-m", "more"])

    monkeypatch.chdir(b)
    capsys.readouterr()
    assert main(["fetch", "origin"]) == 0
    out = capsys.readouterr().out
    assert "origin/main" in out
    assert "fetched" in out


def test_cli_push_from_detached_head_without_branch_arg_errors(tmp_path, monkeypatch, capsys):
    a = tmp_path / "a"
    a.mkdir()
    init_repo(a, monkeypatch)
    b = tmp_path / "b"
    main(["clone", str(a), str(b)])

    monkeypatch.chdir(b)
    sha = repo_mod.current_commit(str(b))
    main(["checkout", sha])
    assert main(["push", "origin"]) == 1
