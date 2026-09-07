import socket
import threading

from ttt.ai_client import run_ai_client
from ttt.server import serve


def _start_server(best_of):
    ready = threading.Event()
    port_holder = []
    t = threading.Thread(
        target=serve,
        args=("127.0.0.1", 0),
        kwargs={"best_of": best_of, "ready_event": ready, "bound_port_holder": port_holder},
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


def test_best_of_three_replays_on_same_connections_until_majority():
    """X wins the top row twice in a row; the match should end 2-0 without a
    third game, and both games must be reachable on the same sockets."""
    _thread, port = _start_server(best_of=3)
    sock_x, fx = _connect(port)
    sock_o, fo = _connect(port)
    try:
        fx.readline()  # WELCOME X
        fx.readline()  # WAITING
        fo.readline()  # WELCOME O
        fx.readline()  # STATE (initial, game 1)
        fo.readline()  # STATE (initial, game 1)

        for game in range(2):
            _move(fx, 0)
            fx.readline()
            fo.readline()
            _move(fo, 3)
            fx.readline()
            fo.readline()
            _move(fx, 1)
            fx.readline()
            fo.readline()
            _move(fo, 4)
            fx.readline()
            fo.readline()
            _move(fx, 2)  # completes top row, X wins this game
            win_x = fx.readline().strip()
            win_o = fo.readline().strip()
            assert win_x == win_o
            assert win_x.endswith("WIN:X")

            score_x = fx.readline().strip()
            score_o = fo.readline().strip()
            assert score_x == score_o == f"SCORE {game + 1} 0"

            if game == 0:
                # match not decided yet (best_of=3 needs 2 wins): board resets
                next_x = fx.readline().strip()
                next_o = fo.readline().strip()
                assert next_x == next_o
                assert next_x.startswith("STATE ......... TURN:X")
            else:
                match_x = fx.readline().strip()
                match_o = fo.readline().strip()
                assert match_x == match_o == "MATCH_OVER X"
    finally:
        fx.close()
        fo.close()
        sock_x.close()
        sock_o.close()


def test_draw_does_not_count_toward_either_score_and_replays():
    _thread, port = _start_server(best_of=3)
    sock_x, fx = _connect(port)
    sock_o, fo = _connect(port)
    try:
        fx.readline()
        fx.readline()
        fo.readline()
        fx.readline()
        fo.readline()

        # X O X / X O O / O X X -> board full, no winner
        moves = [("X", 0), ("O", 1), ("X", 2), ("O", 4), ("X", 3), ("O", 5), ("X", 7), ("O", 6), ("X", 8)]
        for symbol, idx in moves:
            _move(fx if symbol == "X" else fo, idx)
            fx.readline()
            fo.readline()

        score_x = fx.readline().strip()
        score_o = fo.readline().strip()
        assert score_x == score_o == "SCORE 0 0"

        next_x = fx.readline().strip()
        next_o = fo.readline().strip()
        assert next_x == next_o
        assert next_x.startswith("STATE ......... TURN:X")
    finally:
        fx.close()
        fo.close()
        sock_x.close()
        sock_o.close()


def test_two_perfect_ai_clients_tie_the_match_instead_of_looping_forever():
    """Two AIs always draw each other, so nobody would ever reach a majority
    of wins -- the games_played cap must end the match in a TIE."""
    _thread, port = _start_server(best_of=3)
    ai1 = threading.Thread(
        target=run_ai_client, args=("127.0.0.1", port), kwargs={"match": True}, daemon=True
    )
    ai2 = threading.Thread(
        target=run_ai_client, args=("127.0.0.1", port), kwargs={"match": True}, daemon=True
    )
    ai1.start()
    ai2.start()
    # 6 full-depth minimax games (2*best_of) is slow on constrained hardware.
    ai1.join(timeout=60)
    ai2.join(timeout=60)
    assert not ai1.is_alive()
    assert not ai2.is_alive()


def test_ai_client_match_mode_keeps_playing_past_a_single_game():
    """A human filling cells 0..8 in order (skipping taken ones) loses every
    game to the perfect-play AI, so with --best-of the AI should win the
    match 2-0 and both sides should cleanly disconnect once it's decided."""
    _thread, port = _start_server(best_of=3)
    sock_x, fx = _connect(port)
    ai_thread = threading.Thread(
        target=run_ai_client, args=("127.0.0.1", port), kwargs={"match": True}, daemon=True
    )
    ai_thread.start()

    try:
        assert fx.readline().strip() == "WELCOME X"
        assert fx.readline().strip() == "WAITING"
        state = fx.readline().strip()

        games_seen = 0
        while True:
            parts = state.split()
            if parts[0] == "MATCH_OVER":
                assert parts[1] == "O"
                break
            if parts[0] == "SCORE":
                state = fx.readline().strip()
                continue
            cells, status = parts[1], parts[2]
            if status == "TURN:X":
                idx = cells.index(".")
                _move(fx, idx)
            elif status.startswith("WIN:") or status == "DRAW":
                assert not status == "WIN:X"
                games_seen += 1
            state = fx.readline().strip()

        assert games_seen == 2
        ai_thread.join(timeout=5)
        assert not ai_thread.is_alive()
    finally:
        fx.close()
        sock_x.close()
