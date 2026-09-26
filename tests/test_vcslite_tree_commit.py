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


def test_nested_directory_roundtrip(tmp_path):
    rdir = str(tmp_path)
    index = {
        "a.txt": "sha_a",
        "dir/b.txt": "sha_b",
        "dir/sub/c.txt": "sha_c",
        "dir/sub/d.txt": "sha_d",
    }
    sha = tree.write_tree(rdir, index)
    assert tree.read_tree(rdir, sha) == index


def test_unchanged_subdirectory_shares_the_same_tree_object(tmp_path):
    """The whole point of nesting: a subtree untouched between two
    commits should hash identically and be stored only once."""
    rdir = str(tmp_path)
    sha1 = tree.write_tree(rdir, {"dir/a.txt": "sha_a", "top.txt": "v1"})
    sha2 = tree.write_tree(rdir, {"dir/a.txt": "sha_a", "top.txt": "v2"})
    assert sha1 != sha2
    entries1 = {e[1] for e in tree._read_entries(rdir, sha1) if e[0] == "tree"}
    entries2 = {e[1] for e in tree._read_entries(rdir, sha2) if e[0] == "tree"}
    assert entries1 == entries2
    assert len(entries1) == 1


def test_collect_tree_shas_includes_root_and_subtrees(tmp_path):
    rdir = str(tmp_path)
    sha = tree.write_tree(rdir, {"a.txt": "sha_a", "dir/b.txt": "sha_b",
                                  "dir/sub/c.txt": "sha_c"})
    shas = tree.collect_tree_shas(rdir, sha)
    assert sha in shas
    assert len(shas) == 3


def test_collect_tree_shas_flat(tmp_path):
    rdir = str(tmp_path)
    sha = tree.write_tree(rdir, {"a.txt": "sha_a"})
    assert tree.collect_tree_shas(rdir, sha) == {sha}


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
    assert c["parents"] == ["parentsha"]


def test_commit_with_multiple_parents(tmp_path):
    rdir = str(tmp_path)
    sha = commit.write_commit(rdir, "treesha", ["p1", "p2"], "merge", timestamp=300.0)
    c = commit.read_commit(rdir, sha)
    assert c["parents"] == ["p1", "p2"]
    assert c["parent"] == "p1"


def test_commit_message_with_newlines(tmp_path):
    rdir = str(tmp_path)
    sha = commit.write_commit(rdir, "t", None, "line one\nline two", timestamp=1.0)
    c = commit.read_commit(rdir, sha)
    assert c["message"] == "line one\nline two"
