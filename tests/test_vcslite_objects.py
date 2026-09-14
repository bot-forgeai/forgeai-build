from vcslite import objects


def test_hash_object_deterministic():
    a = objects.hash_object(b"hello", "blob")
    b = objects.hash_object(b"hello", "blob")
    assert a == b
    assert len(a) == 40


def test_hash_object_type_affects_hash():
    a = objects.hash_object(b"hello", "blob")
    b = objects.hash_object(b"hello", "tree")
    assert a != b


def test_write_and_read_object_roundtrip(tmp_path):
    rdir = str(tmp_path)
    sha = objects.write_object(rdir, b"hello world", "blob")
    obj_type, data = objects.read_object(rdir, sha)
    assert obj_type == "blob"
    assert data == b"hello world"


def test_write_object_is_idempotent(tmp_path):
    rdir = str(tmp_path)
    sha1 = objects.write_object(rdir, b"same content", "blob")
    sha2 = objects.write_object(rdir, b"same content", "blob")
    assert sha1 == sha2


def test_read_object_missing_raises(tmp_path):
    try:
        objects.read_object(str(tmp_path), "0" * 40)
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_object_exists(tmp_path):
    rdir = str(tmp_path)
    assert not objects.object_exists(rdir, "0" * 40)
    sha = objects.write_object(rdir, b"x", "blob")
    assert objects.object_exists(rdir, sha)
