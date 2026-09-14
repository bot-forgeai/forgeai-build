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


def test_current_branch_defaults_to_main(tmp_path):
    root = repo.init(str(tmp_path))
    assert repo.current_branch(root) == "main"


def test_list_branches_and_branch_exists(tmp_path):
    root = repo.init(str(tmp_path))
    # main isn't a real ref file until the first commit (an "unborn" branch,
    # same idea as git's own behavior on a fresh repo).
    assert repo.list_branches(root) == []
    assert not repo.branch_exists(root, "main")
    repo.write_ref(root, "refs/heads/main", "abc123")
    assert repo.branch_exists(root, "main")
    assert not repo.branch_exists(root, "feature")
    repo.write_ref(root, "refs/heads/feature", "abc123")
    assert repo.list_branches(root) == ["feature", "main"]


def test_set_head_detached_and_current_branch(tmp_path):
    root = repo.init(str(tmp_path))
    repo.write_ref(root, "refs/heads/main", "abc123")
    repo.set_head_detached(root, "abc123")
    assert repo.current_branch(root) is None
    assert repo.current_commit(root) == "abc123"

    repo.set_head_branch(root, "main")
    assert repo.current_branch(root) == "main"
    assert repo.current_commit(root) == "abc123"
