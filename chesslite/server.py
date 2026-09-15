"""TCP server for two-player chess.

Protocol (newline-delimited text, one game per accepted pair of connections):
  server -> client: WELCOME <color>       (w or b)
  server -> client: WAITING               (sent to the first player only)
  server -> both:   STATE <fen> <status>  status: TURN:w, TURN:b, CHECK:w,
                     CHECK:b, CHECKMATE:w, CHECKMATE:b (color = winner),
                     STALEMATE, DRAW
  server -> client: ERROR <message>       (sent only to the client whose move failed)
  server -> other:  OPPONENT_LEFT         (sent if a player disconnects mid-game)
  client -> server: MOVE <coordinate move, e.g. e2e4 or e7e8q for promotion>

<fen> is the position's FEN string with spaces replaced by '_' (see
to_wire/from_wire) so it survives the whitespace-delimited wire format --
it lets a client (human or AI) reconstruct the exact board, including
castling rights and en passant, without replaying move history.
"""
import socket
import threading

from .fen import to_fen
from .game import Game, IllegalMoveError


def to_wire(fen: str) -> str:
    return fen.replace(" ", "_")


def from_wire(token: str) -> str:
    return token.replace("_", " ")


def _send(f, msg):
    f.write(msg + "\n")
    f.flush()


def _status(game):
    result = game.result()
    if result == "checkmate":
        winner = "b" if game.to_move == "w" else "w"
        return f"CHECKMATE:{winner}"
    if result == "stalemate":
        return "STALEMATE"
    if result == "draw":
        return "DRAW"
    if game.in_check():
        return f"CHECK:{game.to_move}"
    return f"TURN:{game.to_move}"


class GameState:
    def __init__(self):
        self.game = Game()
        self.lock = threading.Lock()
        self.conns = {}
        self.socks = {}


def _broadcast_state(state):
    msg = f"STATE {to_wire(to_fen(state.game.board))} {_status(state.game)}"
    for f in state.conns.values():
        try:
            _send(f, msg)
        except (OSError, ValueError):
            pass


def _handle_client(state, color, sock, f):
    try:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if not parts or parts[0] != "MOVE" or len(parts) != 2:
                _send(f, "ERROR bad command")
                continue
            move_text = parts[1].strip()
            with state.lock:
                if state.game.to_move != color:
                    _send(f, "ERROR not your turn")
                    continue
                try:
                    state.game.make_move(move_text)
                except IllegalMoveError as exc:
                    _send(f, f"ERROR {exc}")
                    continue
                _broadcast_state(state)
                if state.game.is_over():
                    break
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        if not state.game.is_over():
            other_color = "b" if color == "w" else "w"
            other_f = state.conns.get(other_color)
            if other_f is not None and other_f is not f:
                try:
                    _send(other_f, "OPPONENT_LEFT")
                except (OSError, ValueError):
                    pass
        try:
            f.close()
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass


def serve(host, port, ready_event=None, bound_port_holder=None):
    """Accepts exactly two connections (white, then black) and runs one
    game to completion, then returns.

    port=0 lets the OS pick a free port; pass bound_port_holder (a list) to
    read the actual bound port back out once ready_event is set. Used by
    both the CLI (fixed port) and tests (ephemeral port).
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(2)
    if bound_port_holder is not None:
        bound_port_holder.append(srv.getsockname()[1])
    if ready_event is not None:
        ready_event.set()

    try:
        state = GameState()
        players = []
        for i, color in enumerate(("w", "b")):
            conn, _addr = srv.accept()
            f = conn.makefile("rw")
            state.conns[color] = f
            state.socks[color] = conn
            _send(f, f"WELCOME {color}")
            if i == 0:
                _send(f, "WAITING")
            players.append((color, conn, f))

        _broadcast_state(state)

        threads = [
            threading.Thread(target=_handle_client, args=(state, color, conn, f), daemon=True)
            for color, conn, f in players
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        srv.close()
