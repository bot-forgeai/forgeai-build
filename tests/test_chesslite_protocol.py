import socket
import threading

from chesslite.fen import from_fen
from chesslite.server import from_wire, serve


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


def _connect(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(("127.0.0.1", port))
    return sock, sock.makefile("rw")


def _move(f, text):
    f.write(f"MOVE {text}\n")
    f.flush()


def test_two_players_connect_and_get_welcomed_and_initial_state():
    _thread, port = _start_server()
    sock_w, fw = _connect(port)
    sock_b, fb = _connect(port)
    try:
        assert fw.readline().strip() == "WELCOME w"
        assert fw.readline().strip() == "WAITING"
        assert fb.readline().strip() == "WELCOME b"

        state_w = fw.readline().strip()
        state_b = fb.readline().strip()
        assert state_w == state_b
        assert state_w.startswith("STATE rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR_w_KQkq_-_0_1 TURN:w")
    finally:
        fw.close()
        fb.close()
        sock_w.close()
        sock_b.close()


def test_a_move_is_broadcast_to_both_players_and_advances_turn():
    _thread, port = _start_server()
    sock_w, fw = _connect(port)
    sock_b, fb = _connect(port)
    try:
        fw.readline()  # WELCOME
        fw.readline()  # WAITING
        fb.readline()  # WELCOME
        fw.readline()  # initial STATE
        fb.readline()  # initial STATE

        _move(fw, "e2e4")
        state_w = fw.readline().strip()
        state_b = fb.readline().strip()
        assert state_w == state_b
        assert "TURN:b" in state_w
        fen = from_wire(state_w.split()[1])
        board = from_fen(fen)
        assert board.piece_at((4, 3)) == "P"
    finally:
        fw.close()
        fb.close()
        sock_w.close()
        sock_b.close()


def test_rejects_move_out_of_turn_with_error():
    _thread, port = _start_server()
    sock_w, fw = _connect(port)
    sock_b, fb = _connect(port)
    try:
        fw.readline()
        fw.readline()
        fb.readline()
        fw.readline()
        fb.readline()

        _move(fb, "e7e5")
        reply = fb.readline().strip()
        assert reply.startswith("ERROR not your turn")
    finally:
        fw.close()
        fb.close()
        sock_w.close()
        sock_b.close()


def test_rejects_illegal_move_with_error():
    _thread, port = _start_server()
    sock_w, fw = _connect(port)
    sock_b, fb = _connect(port)
    try:
        fw.readline()
        fw.readline()
        fb.readline()
        fw.readline()
        fb.readline()

        _move(fw, "e2e5")  # pawns can't jump three squares
        reply = fw.readline().strip()
        assert reply.startswith("ERROR")
    finally:
        fw.close()
        fb.close()
        sock_w.close()
        sock_b.close()


def test_checkmate_ends_game_with_correct_status():
    _thread, port = _start_server()
    sock_w, fw = _connect(port)
    sock_b, fb = _connect(port)
    try:
        fw.readline()
        fw.readline()
        fb.readline()
        fw.readline()
        fb.readline()

        # Fool's Mate: fastest possible checkmate.
        _move(fw, "f2f3")
        fw.readline()
        fb.readline()
        _move(fb, "e7e5")
        fw.readline()
        fb.readline()
        _move(fw, "g2g4")
        fw.readline()
        fb.readline()
        _move(fb, "d8h4")

        last_w = fw.readline().strip()
        last_b = fb.readline().strip()
        assert last_w == last_b
        assert last_w.endswith("CHECKMATE:b")
    finally:
        fw.close()
        fb.close()
        sock_w.close()
        sock_b.close()


def test_opponent_disconnect_notifies_remaining_player():
    _thread, port = _start_server()
    sock_w, fw = _connect(port)
    sock_b, fb = _connect(port)
    try:
        fw.readline()
        fw.readline()
        fb.readline()
        fw.readline()
        fb.readline()

        sock_b.shutdown(socket.SHUT_RDWR)
        fb.close()
        sock_b.close()
        notice = fw.readline().strip()
        assert notice == "OPPONENT_LEFT"
    finally:
        fw.close()
        sock_w.close()
