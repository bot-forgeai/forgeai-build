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


def test_init(project, capsys):
    assert main(["init"]) == 0
    assert os.path.isdir(".vcslite")
    out = capsys.readouterr().out
    assert "initialized" in out


def test_init_twice_errors(project):
    main(["init"])
    assert main(["init"]) == 1


def test_add_and_status(project, capsys):
    main(["init"])
    write("a.txt", "hello")
    assert main(["add", "a.txt"]) == 0
    capsys.readouterr()
    main(["status"])
    out = capsys.readouterr().out
    assert "staged for commit" in out
    assert "a.txt" in out


def test_commit_then_clean_status(project, capsys):
    main(["init"])
    write("a.txt", "hello")
    main(["add", "a.txt"])
    capsys.readouterr()
    assert main(["commit", "-m", "first commit"]) == 0
    out = capsys.readouterr().out
    assert "first commit" in out

    main(["status"])
    out = capsys.readouterr().out
    assert "nothing to commit" in out


def test_commit_nothing_staged_errors(project, capsys):
    main(["init"])
    assert main(["commit", "-m", "empty"]) == 1


def test_untracked_and_modified_detection(project, capsys):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "v1"])
    capsys.readouterr()

    write("a.txt", "v2")
    write("b.txt", "new file")
    main(["status"])
    out = capsys.readouterr().out
    assert "modified, not staged" in out
    assert "a.txt" in out
    assert "untracked" in out
    assert "b.txt" in out


def test_log_shows_commit_chain(project, capsys):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    write("a.txt", "v2")
    main(["add", "a.txt"])
    main(["commit", "-m", "second"])
    capsys.readouterr()

    main(["log"])
    out = capsys.readouterr().out
    assert "first" in out
    assert "second" in out
    assert out.index("second") < out.index("first")


def test_checkout_restores_earlier_version(project, capsys):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])

    with open(".vcslite/refs/heads/main") as f:
        first_sha = f.read().strip()

    write("a.txt", "v2")
    main(["add", "a.txt"])
    main(["commit", "-m", "second"])

    with open("a.txt") as f:
        assert f.read() == "v2"

    capsys.readouterr()
    assert main(["checkout", first_sha]) == 0
    with open("a.txt") as f:
        assert f.read() == "v1"


def test_checkout_removes_files_added_later(project):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    with open(".vcslite/refs/heads/main") as f:
        first_sha = f.read().strip()

    write("b.txt", "new")
    main(["add", "a.txt", "b.txt"])
    main(["commit", "-m", "second"])
    assert os.path.exists("b.txt")

    main(["checkout", first_sha])
    assert not os.path.exists("b.txt")


def test_checkout_short_prefix(project, capsys):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    with open(".vcslite/refs/heads/main") as f:
        full_sha = f.read().strip()

    capsys.readouterr()
    assert main(["checkout", full_sha[:8]]) == 0


def test_checkout_unknown_sha_errors(project, capsys):
    main(["init"])
    assert main(["checkout", "deadbeef"]) == 1


def test_diff_shows_unified_diff(project, capsys):
    main(["init"])
    write("a.txt", "line1\nline2\n")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])

    write("a.txt", "line1\nchanged\n")
    main(["add", "a.txt"])
    capsys.readouterr()
    main(["diff"])
    out = capsys.readouterr().out
    assert "-line2" in out
    assert "+changed" in out


def test_diff_no_changes(project, capsys):
    main(["init"])
    write("a.txt", "content")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    capsys.readouterr()
    main(["diff"])
    out = capsys.readouterr().out
    assert "no staged changes" in out


def test_add_dot_stages_everything(project, capsys):
    main(["init"])
    write("a.txt", "a")
    write("b.txt", "b")
    assert main(["add", "."]) == 0
    capsys.readouterr()
    main(["status"])
    out = capsys.readouterr().out
    assert "a.txt" in out and "b.txt" in out


def test_add_missing_file_errors(project):
    main(["init"])
    assert main(["add", "nope.txt"]) == 1


def test_branch_list_shows_main_and_marks_current(project, capsys):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    capsys.readouterr()

    main(["branch"])
    out = capsys.readouterr().out
    assert "* main" in out


def test_branch_create_before_first_commit_errors(project):
    main(["init"])
    assert main(["branch", "feature"]) == 1


def test_branch_create_and_list(project, capsys):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    capsys.readouterr()

    assert main(["branch", "feature"]) == 0
    main(["branch"])
    out = capsys.readouterr().out
    assert "* main" in out
    assert "feature" in out


def test_branch_duplicate_name_errors(project):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    main(["branch", "feature"])
    assert main(["branch", "feature"]) == 1


def test_checkout_branch_switches_head_and_files(project, capsys):
    main(["init"])
    write("a.txt", "on-main")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    main(["branch", "feature"])
    main(["checkout", "feature"])
    write("a.txt", "on-feature")
    main(["add", "a.txt"])
    main(["commit", "-m", "second"])

    capsys.readouterr()
    assert main(["checkout", "main"]) == 0
    with open("a.txt") as f:
        assert f.read() == "on-main"

    main(["status"])
    out = capsys.readouterr().out
    assert "on branch main" in out


def test_checkout_new_branch_flag(project, capsys):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])

    capsys.readouterr()
    assert main(["checkout", "-b", "feature"]) == 0
    main(["status"])
    out = capsys.readouterr().out
    assert "on branch feature" in out

    main(["branch"])
    out = capsys.readouterr().out
    assert "* feature" in out
    assert "main" in out


def test_commits_on_separate_branches_dont_move_each_other(project):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    with open(".vcslite/refs/heads/main") as f:
        main_sha = f.read().strip()

    main(["checkout", "-b", "feature"])
    write("a.txt", "v2")
    main(["add", "a.txt"])
    main(["commit", "-m", "second"])

    with open(".vcslite/refs/heads/main") as f:
        assert f.read().strip() == main_sha
    with open(".vcslite/refs/heads/feature") as f:
        assert f.read().strip() != main_sha


def test_checkout_detached_then_commit_does_not_move_branch(project):
    main(["init"])
    write("a.txt", "v1")
    main(["add", "a.txt"])
    main(["commit", "-m", "first"])
    with open(".vcslite/refs/heads/main") as f:
        first_sha = f.read().strip()

    write("a.txt", "v2")
    main(["add", "a.txt"])
    main(["commit", "-m", "second"])
    with open(".vcslite/refs/heads/main") as f:
        second_sha = f.read().strip()

    main(["checkout", first_sha])
    write("a.txt", "detached-edit")
    main(["add", "a.txt"])
    main(["commit", "-m", "detached commit"])

    with open(".vcslite/refs/heads/main") as f:
        main_sha_after = f.read().strip()
    assert main_sha_after == second_sha


def test_checkout_unknown_branch_falls_back_to_sha_error(project):
    main(["init"])
    assert main(["checkout", "nope"]) == 1


def test_checkout_no_args_errors(project):
    main(["init"])
    assert main(["checkout"]) == 1
