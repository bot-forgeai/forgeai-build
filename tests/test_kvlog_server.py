import threading

import pytest

from kvlog.client import RemoteError, call
from kvlog.server import KVServer


@pytest.fixture
def running_server(tmp_path):
    db_path = str(tmp_path / "net.db")
    server = KVServer(("127.0.0.1", 0), db_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield host, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_put_and_get_over_network(running_server):
    host, port = running_server
    call(host, port, "put", key="name", value="ada")
    response = call(host, port, "get", key="name")
    assert response["value"] == "ada"


def test_get_missing_key_raises(running_server):
    host, port = running_server
    with pytest.raises(RemoteError):
        call(host, port, "get", key="nope")


def test_delete_over_network(running_server):
    host, port = running_server
    call(host, port, "put", key="x", value="1")
    call(host, port, "delete", key="x")
    with pytest.raises(RemoteError):
        call(host, port, "get", key="x")


def test_keys_dump_prefix_range_over_network(running_server):
    host, port = running_server
    call(host, port, "put", key="user:1", value="ada")
    call(host, port, "put", key="user:2", value="bob")
    assert call(host, port, "keys")["keys"] == ["user:1", "user:2"]
    assert call(host, port, "dump")["items"] == [["user:1", "ada"], ["user:2", "bob"]]
    assert call(host, port, "prefix", prefix="user:")["items"] == [
        ["user:1", "ada"],
        ["user:2", "bob"],
    ]
    assert call(host, port, "range", start="user:1", end="user:1")["items"] == [
        ["user:1", "ada"]
    ]


def test_compact_over_network(running_server):
    host, port = running_server
    for i in range(5):
        call(host, port, "put", key="k", value=str(i))
    response = call(host, port, "compact")
    assert response["count"] == 1


def test_multiple_clients_share_state(running_server):
    host, port = running_server
    call(host, port, "put", key="shared", value="1")
    # A second, independent connection sees the same store.
    response = call(host, port, "get", key="shared")
    assert response["value"] == "1"


def test_concurrent_puts_are_serialized(running_server):
    host, port = running_server

    def worker(n):
        for i in range(20):
            call(host, port, "put", key=f"k{n}", value=str(i))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    keys = call(host, port, "keys")["keys"]
    assert keys == sorted(f"k{n}" for n in range(5))
