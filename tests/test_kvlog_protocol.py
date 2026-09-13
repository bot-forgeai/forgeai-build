from kvlog.protocol import dispatch
from kvlog.store import KVStore


def test_put_and_get(tmp_path):
    with KVStore(str(tmp_path / "db")) as store:
        assert dispatch(store, {"op": "put", "key": "a", "value": "1"}) == {"ok": True}
        assert dispatch(store, {"op": "get", "key": "a"}) == {"ok": True, "value": "1"}


def test_get_missing_key(tmp_path):
    with KVStore(str(tmp_path / "db")) as store:
        response = dispatch(store, {"op": "get", "key": "nope"})
        assert response["ok"] is False
        assert "nope" in response["error"]


def test_delete(tmp_path):
    with KVStore(str(tmp_path / "db")) as store:
        dispatch(store, {"op": "put", "key": "a", "value": "1"})
        assert dispatch(store, {"op": "delete", "key": "a"}) == {"ok": True}
        response = dispatch(store, {"op": "delete", "key": "a"})
        assert response["ok"] is False


def test_keys_and_dump(tmp_path):
    with KVStore(str(tmp_path / "db")) as store:
        dispatch(store, {"op": "put", "key": "a", "value": "1"})
        dispatch(store, {"op": "put", "key": "b", "value": "2"})
        assert dispatch(store, {"op": "keys"}) == {"ok": True, "keys": ["a", "b"]}
        response = dispatch(store, {"op": "dump"})
        assert response == {"ok": True, "items": [("a", "1"), ("b", "2")]}


def test_prefix_and_range(tmp_path):
    with KVStore(str(tmp_path / "db")) as store:
        for k in ["user:1", "user:2", "group:1"]:
            dispatch(store, {"op": "put", "key": k, "value": k})
        response = dispatch(store, {"op": "prefix", "prefix": "user:"})
        assert response == {"ok": True, "items": [("user:1", "user:1"), ("user:2", "user:2")]}
        response = dispatch(store, {"op": "range", "start": "group:1", "end": "user:1"})
        assert response == {"ok": True, "items": [("group:1", "group:1"), ("user:1", "user:1")]}


def test_compact(tmp_path):
    db_path = str(tmp_path / "db")
    with KVStore(db_path) as store:
        for i in range(5):
            dispatch(store, {"op": "put", "key": "k", "value": str(i)})
        response = dispatch(store, {"op": "compact"})
        assert response["ok"] is True
        assert response["count"] == 1
        assert response["after"] <= response["before"]


def test_unknown_op(tmp_path):
    with KVStore(str(tmp_path / "db")) as store:
        response = dispatch(store, {"op": "bogus"})
        assert response["ok"] is False
        assert "bogus" in response["error"]
