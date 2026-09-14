import os

import pytest

from vcslite import worktree


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_load_ignore_patterns_missing_file(project):
    assert worktree.load_ignore_patterns(str(project)) == []


def test_load_ignore_patterns_skips_blank_and_comment_lines(project):
    (project / ".vcsliteignore").write_text("# comment\n\n*.log\nbuild/\n")
    assert worktree.load_ignore_patterns(str(project)) == ["*.log", "build/"]


def test_is_ignored_matches_extension_glob():
    assert worktree.is_ignored("a/b/debug.log", ["*.log"])
    assert not worktree.is_ignored("a/b/debug.txt", ["*.log"])


def test_is_ignored_matches_directory_component_anywhere():
    assert worktree.is_ignored("build/out.o", ["build/"])
    assert worktree.is_ignored("nested/build/out.o", ["build"])
    assert not worktree.is_ignored("rebuild/out.o", ["build"])


def test_list_addable_files_excludes_ignored(project):
    (project / ".vcsliteignore").write_text("*.log\n")
    (project / "a.txt").write_text("a")
    (project / "debug.log").write_text("noisy")
    files = worktree.list_addable_files(str(project))
    assert "a.txt" in files
    assert "debug.log" not in files
