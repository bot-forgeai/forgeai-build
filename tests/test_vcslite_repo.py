import os

import pytest

from vcslite import repo


def test_init_creates_structure(tmp_path):
    root = repo.init(str(tmp_path))
    vdir = repo.repo_dir(root)
    assert os.path.isdir(os.path.join(vdir, "objects"))
    assert os.path.isdir(os.path.join(vdir, "refs", "heads"))
    assert os.path.isfile(os.path.join(vdir, "HEAD"))


def test_init_twice_raises(tmp_path):
    repo.init(str(tmp_path))
    with pytest.raises(FileExistsError):
        repo.init(str(tmp_path))


def test_find_repo_root_from_subdir(tmp_path):
    root = repo.init(str(tmp_path))
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    found = repo.find_repo_root(str(sub))
    assert found == root


def test_find_repo_root_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        repo.find_repo_root(str(tmp_path))


def test_head_ref_and_current_commit(tmp_path):
    root = repo.init(str(tmp_path))
    assert repo.read_head_ref(root) == "refs/heads/main"
    assert repo.current_commit(root) is None
    repo.write_ref(root, "refs/heads/main", "abc123")
    assert repo.current_commit(root) == "abc123"
