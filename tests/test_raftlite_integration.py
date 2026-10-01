import socket
import time

import pytest

from raftlite.server import RaftServer
from raftlite.transport import client_request


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def make_cluster(n=3, election_timeout_range=(4, 8)):
    ports = {i: free_port() for i in range(n)}
    servers = {}
    for i in range(n):
        peers = {j: ("127.0.0.1", ports[j]) for j in range(n) if j != i}
        servers[i] = RaftServer(i, ("127.0.0.1", ports[i]), peers,
                                 election_timeout_range=election_timeout_range,
                                 heartbeat_interval=2)
    for s in servers.values():
        s.start()
    return servers, ports


def wait_for_leader(servers, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for nid, s in servers.items():
            with s.lock:
                if s.node.role == "leader":
                    return nid
        time.sleep(0.05)
    raise AssertionError("no leader elected within timeout")


@pytest.fixture
def cluster():
    servers, ports = make_cluster()
    yield servers, ports
    for s in servers.values():
        s.stop()


def test_cluster_elects_a_single_leader(cluster):
    servers, ports = cluster
    leader_id = wait_for_leader(servers)
    with servers[leader_id].lock:
        term = servers[leader_id].node.current_term
    time.sleep(0.3)
    leaders = [nid for nid, s in servers.items() if s.node.role == "leader"]
    assert leaders == [leader_id]
    for nid, s in servers.items():
        if nid != leader_id:
            assert s.node.current_term == term


def test_put_and_get_round_trip(cluster):
    servers, ports = cluster
    leader_id = wait_for_leader(servers)
    addr = ("127.0.0.1", ports[leader_id])

    response = client_request(addr, {"type": "PUT", "key": "foo", "value": "bar"})
    assert response["status"] == "OK"

    get_response = client_request(addr, {"type": "GET", "key": "foo"})
    assert get_response["found"] is True
    assert get_response["value"] == "bar"


def test_put_replicates_to_followers(cluster):
    servers, ports = cluster
    leader_id = wait_for_leader(servers)
    addr = ("127.0.0.1", ports[leader_id])
    client_request(addr, {"type": "PUT", "key": "k", "value": "v"})

    deadline = time.monotonic() + 3.0
    for nid, s in servers.items():
        if nid == leader_id:
            continue
        while time.monotonic() < deadline and s.kv.get("k") != "v":
            time.sleep(0.05)
        assert s.kv.get("k") == "v", f"node {nid} never replicated the write"


def test_put_rejected_by_non_leader(cluster):
    servers, ports = cluster
    leader_id = wait_for_leader(servers)
    follower_id = next(nid for nid in servers if nid != leader_id)
    addr = ("127.0.0.1", ports[follower_id])
    response = client_request(addr, {"type": "PUT", "key": "x", "value": "1"})
    assert response["status"] == "NOT_LEADER"


def test_new_leader_elected_after_leader_stops(cluster):
    servers, ports = cluster
    leader_id = wait_for_leader(servers)
    old_term = servers[leader_id].node.current_term
    servers[leader_id].stop()

    deadline = time.monotonic() + 5.0
    new_leader_id = None
    while time.monotonic() < deadline:
        leaders = [nid for nid, s in servers.items()
                   if nid != leader_id and s.node.role == "leader"]
        if leaders:
            new_leader_id = leaders[0]
            break
        time.sleep(0.05)
    assert new_leader_id is not None, "no new leader elected after the old leader stopped"
    assert servers[new_leader_id].node.current_term > old_term


def test_status_request(cluster):
    servers, ports = cluster
    leader_id = wait_for_leader(servers)
    response = client_request(("127.0.0.1", ports[leader_id]), {"type": "STATUS"})
    assert response["role"] == "leader"
    assert response["leader_id"] == leader_id
