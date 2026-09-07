import socket
import threading

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


def _move(f, idx):
    f.write(f"MOVE {idx}\n")
    f.flush()


def test_two_players_can_connect_and_play_to_a_win():
    _thread, port = _start_server()
    sock_x, fx = _connect(port)
    sock_o, fo = _connect(port)
    try:
        assert fx.readline().strip() == "WELCOME X"
        assert fx.readline().strip() == "WAITING"
        assert fo.readline().strip() == "WELCOME O"

        assert fx.readline().strip().startswith("STATE ......... TURN:X")
        assert fo.readline().strip().startswith("STATE ......... TURN:X")

        _move(fx, 0)
        assert fx.readline().strip() == "STATE X........ TURN:O"
        assert fo.readline().strip() == "STATE X........ TURN:O"

        _move(fo, 3)
        assert fx.readline().strip() == "STATE X..O..... TURN:X"
        assert fo.readline().strip() == "STATE X..O..... TURN:X"

        _move(fx, 1)
        fx.readline()
        fo.readline()
        _move(fo, 4)
        fx.readline()
        fo.readline()
        _move(fx, 2)

        last_x = fx.readline().strip()
        last_o = fo.readline().strip()
        assert last_x == last_o
        assert last_x.endswith("WIN:X")
    finally:
        fx.close()
        fo.close()
        sock_x.close()
        sock_o.close()


def test_rejects_move_out_of_turn_with_error():
    _thread, port = _start_server()
    sock_x, fx = _connect(port)
    sock_o, fo = _connect(port)
    try:
        fx.readline()  # WELCOME X
        fx.readline()  # WAITING
        fo.readline()  # WELCOME O
        fx.readline()  # STATE
        fo.readline()  # STATE

        _move(fo, 0)
        reply = fo.readline().strip()
        assert reply.startswith("ERROR")
    finally:
        fx.close()
        fo.close()
        sock_x.close()
        sock_o.close()


def test_rejects_occupied_cell_with_error():
    _thread, port = _start_server()
    sock_x, fx = _connect(port)
    sock_o, fo = _connect(port)
    try:
        fx.readline()
        fx.readline()
        fo.readline()
        fx.readline()
        fo.readline()

        _move(fx, 0)
        fx.readline()
        fo.readline()

        _move(fo, 0)
        reply = fo.readline().strip()
        assert reply.startswith("ERROR")
    finally:
        fx.close()
        fo.close()
        sock_x.close()
        sock_o.close()


def test_opponent_disconnect_notifies_remaining_player():
    _thread, port = _start_server()
    sock_x, fx = _connect(port)
    sock_o, fo = _connect(port)
    try:
        fx.readline()
        fx.readline()
        fo.readline()
        fx.readline()
        fo.readline()

        sock_o.shutdown(socket.SHUT_RDWR)
        fo.close()
        sock_o.close()
        notice = fx.readline().strip()
        assert notice == "OPPONENT_LEFT"
    finally:
        fx.close()
        sock_x.close()


def test_third_connection_joins_as_spectator_and_sees_state():
    _thread, port = _start_server()
    sock_x, fx = _connect(port)
    sock_o, fo = _connect(port)
    try:
        fx.readline()  # WELCOME X
        fx.readline()  # WAITING
        fo.readline()  # WELCOME O
        fx.readline()  # STATE (initial)
        fo.readline()  # STATE (initial)

        sock_spec, fspec = _connect(port)
        try:
            assert fspec.readline().strip() == "WELCOME SPECTATOR"
            assert fspec.readline().strip().startswith("STATE ......... TURN:X")

            _move(fx, 0)
            fx.readline()
            fo.readline()
            assert fspec.readline().strip() == "STATE X........ TURN:O"
        finally:
            fspec.close()
            sock_spec.close()
    finally:
        fx.close()
        fo.close()
        sock_x.close()
        sock_o.close()


def test_spectator_move_command_is_ignored_not_applied():
    _thread, port = _start_server()
    sock_x, fx = _connect(port)
    sock_o, fo = _connect(port)
    try:
        fx.readline()
        fx.readline()
        fo.readline()
        fx.readline()
        fo.readline()

        sock_spec, fspec = _connect(port)
        try:
            fspec.readline()  # WELCOME SPECTATOR
            fspec.readline()  # STATE

            fspec.write("MOVE 0\n")
            fspec.flush()

            # The board is untouched: a real player move still lands on X's turn.
            _move(fx, 0)
            assert fx.readline().strip() == "STATE X........ TURN:O"
        finally:
            fspec.close()
            sock_spec.close()
    finally:
        fx.close()
        fo.close()
        sock_x.close()
        sock_o.close()


def test_spectator_notified_on_opponent_left():
    _thread, port = _start_server()
    sock_x, fx = _connect(port)
    sock_o, fo = _connect(port)
    try:
        fx.readline()
        fx.readline()
        fo.readline()
        fx.readline()
        fo.readline()

        sock_spec, fspec = _connect(port)
        try:
            fspec.readline()  # WELCOME SPECTATOR
            fspec.readline()  # STATE

            sock_o.shutdown(socket.SHUT_RDWR)
            fo.close()
            sock_o.close()

            assert fspec.readline().strip() == "OPPONENT_LEFT"
        finally:
            fspec.close()
            sock_spec.close()
    finally:
        fx.close()
        sock_x.close()
