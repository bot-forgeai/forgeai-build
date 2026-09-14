import os

import pytest

from vcslite.__main__ import main


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write(path, content):
    with open(path, "w") as f:
        f.write(content)


def read(path):
    with open(path) as f:
        return f.read()


def test_merge_fast_forward(project, capsys):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    main(["checkout", "-b", "feature"])
    write("a.txt", "v2")
    main(["add", "a.txt"])
    main(["commit", "-m", "second"])
    main(["checkout", "main"])

    capsys.readouterr()
    assert main(["merge", "feature"]) == 0
    out = capsys.readouterr().out
    assert "fast-forwarded" in out
    assert read("a.txt") == "v2"


def test_merge_already_up_to_date(project, capsys):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    main(["branch", "feature"])

    capsys.readouterr()
    assert main(["merge", "feature"]) == 0
    out = capsys.readouterr().out
    assert "already up to date" in out


def test_merge_clean_three_way(project, capsys):
    main(["init"])
    write("a.txt", "base")
    write("b.txt", "base-b")
    main(["add", "."])
    main(["commit", "-m", "base"])

    main(["checkout", "-b", "feature"])
    write("b.txt", "changed-on-feature")
    main(["add", "b.txt"])
    main(["commit", "-m", "feature change"])

    main(["checkout", "main"])
    write("a.txt", "changed-on-main")
    main(["add", "a.txt"])
    main(["commit", "-m", "main change"])

    capsys.readouterr()
    assert main(["merge", "feature"]) == 0
    out = capsys.readouterr().out
    assert "merged feature into main" in out
    assert read("a.txt") == "changed-on-main"
    assert read("b.txt") == "changed-on-feature"

    main(["log"])
    out = capsys.readouterr().out
    assert "merge:" in out


def test_merge_conflict_writes_markers_and_blocks_commit(project, capsys):
    main(["init"])
    write("a.txt", "base")
    main(["add", "a.txt"])
    main(["commit", "-m", "base"])

    main(["checkout", "-b", "feature"])
    write("a.txt", "feature-version")
    main(["add", "a.txt"])
    main(["commit", "-m", "feature edit"])

    main(["checkout", "main"])
    write("a.txt", "main-version")
    main(["add", "a.txt"])
    main(["commit", "-m", "main edit"])

    capsys.readouterr()
    assert main(["merge", "feature"]) == 1
    out = capsys.readouterr().out
    assert "conflict" in out
    assert "a.txt" in out

    content = read("a.txt")
    assert "<<<<<<< HEAD" in content
    assert "main-version" in content
    assert "=======" in content
    assert "feature-version" in content
    assert ">>>>>>> feature" in content

    capsys.readouterr()
    main(["status"])
    out = capsys.readouterr().out
    assert "merging" in out
    assert "conflicted" in out
    assert "a.txt" in out


def test_merge_resolve_conflict_then_commit(project, capsys):
    main(["init"])
    write("a.txt", "base")
    main(["add", "a.txt"])
    main(["commit", "-m", "base"])

    main(["checkout", "-b", "feature"])
    write("a.txt", "feature-version")
    main(["add", "a.txt"])
    main(["commit", "-m", "feature edit"])

    main(["checkout", "main"])
    write("a.txt", "main-version")
    main(["add", "a.txt"])
    main(["commit", "-m", "main edit"])

    main(["merge", "feature"])
    write("a.txt", "resolved-version")
    main(["add", "a.txt"])

    capsys.readouterr()
    assert main(["commit", "-m", "resolve merge"]) == 0

    main(["status"])
    out = capsys.readouterr().out
    assert "merging" not in out


def test_merge_second_merge_while_unresolved_errors(project, capsys):
    main(["init"])
    write("a.txt", "base")
    main(["add", "a.txt"])
    main(["commit", "-m", "base"])

    main(["checkout", "-b", "feature"])
    write("a.txt", "feature-version")
    main(["add", "a.txt"])
    main(["commit", "-m", "feature edit"])

    main(["checkout", "main"])
    write("a.txt", "main-version")
    main(["add", "a.txt"])
    main(["commit", "-m", "main edit"])

    main(["merge", "feature"])
    capsys.readouterr()
    assert main(["merge", "feature"]) == 1
    err = capsys.readouterr().err
    assert "already in progress" in err


def test_merge_abort_restores_working_tree(project, capsys):
    main(["init"])
    write("a.txt", "base")
    main(["add", "a.txt"])
    main(["commit", "-m", "base"])

    main(["checkout", "-b", "feature"])
    write("a.txt", "feature-version")
    main(["add", "a.txt"])
    main(["commit", "-m", "feature edit"])

    main(["checkout", "main"])
    write("a.txt", "main-version")
    main(["add", "a.txt"])
    main(["commit", "-m", "main edit"])

    main(["merge", "feature"])
    capsys.readouterr()
    assert main(["merge", "--abort"]) == 0
    out = capsys.readouterr().out
    assert "aborted" in out
    assert read("a.txt") == "main-version"

    main(["status"])
    out = capsys.readouterr().out
    assert "merging" not in out


def test_merge_abort_without_merge_errors(project):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    assert main(["merge", "--abort"]) == 1


def test_merge_detached_head_errors(project):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    with open(".vcslite/refs/heads/main") as f:
        sha = f.read().strip()
    main(["branch", "feature"])
    main(["checkout", sha])
    assert main(["merge", "feature"]) == 1


def test_merge_unknown_branch_errors(project):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    assert main(["merge", "nope"]) == 1


def test_merge_no_args_errors(project):
    main(["init"])
    assert main(["merge"]) == 1
