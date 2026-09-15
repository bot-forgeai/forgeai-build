import threading

from chesslite.ai_client import run_ai_client
from chesslite.server import serve


def _start_server():
    ready = threading.Event()
    port_holder = []
    t = threading.Thread(
        target=serve,
        args=("127.0.0.1", 0),
        kwargs={"ready_event": ready, "bound_port_holder": port_holder},
        daemon=True,
    )
    t.start()
    assert ready.wait(timeout=5)
    return t, port_holder[0]


def test_two_ai_clients_play_a_full_game_and_both_exit_cleanly():
    _thread, port = _start_server()
    ai_w = threading.Thread(
        target=run_ai_client, args=("127.0.0.1", port), kwargs={"depth": 1}, daemon=True,
    )
    ai_b = threading.Thread(
        target=run_ai_client, args=("127.0.0.1", port), kwargs={"depth": 1}, daemon=True,
    )
    ai_w.start()
    ai_b.start()
    ai_w.join(timeout=60)
    ai_b.join(timeout=60)
    assert not ai_w.is_alive()
    assert not ai_b.is_alive()
