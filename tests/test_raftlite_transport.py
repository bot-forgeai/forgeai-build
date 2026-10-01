import socket
import threading
import time

from raftlite.transport import Transport


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_peer_link_survives_idle_period_past_connect_timeout():
    """Regression test: socket.create_connection(..., timeout=2) leaves the
    connect() timeout active on the socket for all future operations unless
    explicitly cleared. That silently killed a connecting node's reader
    thread (via a swallowed socket.timeout/OSError) after any idle gap
    longer than 2s -- exactly what happens mid-election when peers go quiet
    for a bit. This waits past that threshold and confirms the link still
    works afterward.
    """
    port_a = free_port()
    port_b = free_port()
    received = []
    lock = threading.Lock()

    def on_msg_a(sender, msg):
        pass

    def on_msg_b(sender, msg):
        with lock:
            received.append((sender, msg))

    def on_client(msg):
        return {"status": "OK"}

    # node 1 is the one whose socket.create_connection(timeout=2) call put a
    # stale read timeout on its own outbound link (id 0 < id 1, so node 1 is
    # the connector per Transport's "higher id connects to lower id" rule) --
    # the bug only shows up on the *connecting* side's ability to keep
    # receiving, so node 0 must be the one sending, after the idle gap.
    t_a = Transport(0, ("127.0.0.1", port_a), {1: ("127.0.0.1", port_b)}, on_msg_a, on_client)
    t_b = Transport(1, ("127.0.0.1", port_b), {0: ("127.0.0.1", port_a)}, on_msg_b, on_client)
    t_a.start()
    t_b.start()
    try:
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and (0 not in t_b.links or 1 not in t_a.links):
            time.sleep(0.05)
        assert 0 in t_b.links and 1 in t_a.links, "peer link never established"

        time.sleep(2.5)  # longer than the old lingering connect() timeout

        assert t_a.send(1, {"type": "ping"})
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not received:
            time.sleep(0.05)
        assert received == [(0, {"type": "ping"})]
    finally:
        t_a.stop()
        t_b.stop()
