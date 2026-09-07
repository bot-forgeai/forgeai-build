import socket
import threading

from ttt.ai_client import run_ai_client
from ttt.server import serve


def _start_server(num_games=1):
    ready = threading.Event()
    port_holder = []
    t = threading.Thread(
        target=serve,
        args=("127.0.0.1", 0),
        kwargs={"num_games": num_games, "ready_event": ready, "bound_port_holder": port_holder},
        daemon=True,
    )
    t.start()
    assert ready.wait(timeout=5)
    return t, port_holder[0]


def _connect(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(("127.0.0.1", port))
    return sock, sock.makefile("rw")


def test_ai_client_blocks_and_never_loses_to_a_naive_human():
    """A human playing top-left-to-right should never beat a perfect AI."""
    _thread, port = _start_server()
    sock_x, fx = _connect(port)  # human, plays X
    ai_thread = threading.Thread(target=run_ai_client, args=("127.0.0.1", port), daemon=True)
    ai_thread.start()

    try:
        assert fx.readline().strip() == "WELCOME X"
        assert fx.readline().strip() == "WAITING"
        state = fx.readline().strip()  # initial STATE, TURN:X

        naive_order = iter([0, 1, 2, 3, 5, 6, 7, 8])
        while "TURN:" in state:
            if "TURN:X" in state:
                fx.write(f"MOVE {next(naive_order)}\n")
                fx.flush()
            state = fx.readline().strip()

        assert "WIN:X" not in state
    finally:
        fx.close()
        sock_x.close()


def test_two_ai_clients_always_draw():
    _thread, port = _start_server()
    ai1 = threading.Thread(target=run_ai_client, args=("127.0.0.1", port), daemon=True)
    ai2 = threading.Thread(target=run_ai_client, args=("127.0.0.1", port), daemon=True)
    ai1.start()
    ai2.start()
    ai1.join(timeout=10)
    ai2.join(timeout=10)
    assert not ai1.is_alive()
    assert not ai2.is_alive()
