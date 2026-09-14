from vcslite import commit, tree


def test_tree_roundtrip(tmp_path):
    rdir = str(tmp_path)
    index = {"a.txt": "sha_a", "dir/b.txt": "sha_b"}
    sha = tree.write_tree(rdir, index)
    result = tree.read_tree(rdir, sha)
    assert result == index


def test_empty_tree_roundtrip(tmp_path):
    rdir = str(tmp_path)
    sha = tree.write_tree(rdir, {})
    assert tree.read_tree(rdir, sha) == {}


def test_tree_is_deterministic_regardless_of_dict_order(tmp_path):
    rdir = str(tmp_path)
    sha1 = tree.write_tree(rdir, {"a": "1", "b": "2"})
    sha2 = tree.write_tree(rdir, {"b": "2", "a": "1"})
    assert sha1 == sha2


def test_commit_roundtrip(tmp_path):
    rdir = str(tmp_path)
    sha = commit.write_commit(rdir, "treesha", None, "initial commit", timestamp=100.0)
    c = commit.read_commit(rdir, sha)
    assert c["tree"] == "treesha"
    assert c["parent"] is None
    assert c["message"] == "initial commit"
    assert c["timestamp"] == 100.0


def test_commit_with_parent(tmp_path):
    rdir = str(tmp_path)
    sha = commit.write_commit(rdir, "treesha", "parentsha", "second", timestamp=200.0)
    c = commit.read_commit(rdir, sha)
    assert c["parent"] == "parentsha"


def test_commit_message_with_newlines(tmp_path):
    rdir = str(tmp_path)
    sha = commit.write_commit(rdir, "t", None, "line one\nline two", timestamp=1.0)
    c = commit.read_commit(rdir, sha)
    assert c["message"] == "line one\nline two"
