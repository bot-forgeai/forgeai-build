"""TCP server for two-player tic-tac-toe.

Protocol (newline-delimited text, one game at a time per accepted pair):
  server -> client: WELCOME <symbol>
  server -> client: WAITING                      (sent to the first player only)
  server -> both:   STATE <9-char board> <status> (status: TURN:X, TURN:O, WIN:X, WIN:O, DRAW)
  server -> client: ERROR <message>               (sent only to the client whose move failed)
  server -> other:  OPPONENT_LEFT                 (sent if a player disconnects mid-game)
  client -> server: MOVE <0-8>

  Any connection accepted while a game already has both players is treated
  as a spectator instead of a third player:
  server -> spectator: WELCOME SPECTATOR
  server -> spectator: STATE ... / OPPONENT_LEFT  (same broadcasts as players, read-only)
"""
import queue
import socket
import threading

from .board import Board, InvalidMove


class Game:
    def __init__(self):
        self.board = Board()
        self.lock = threading.Lock()
        self.conns = {}
        self.spectators = []
        self.spectators_lock = threading.Lock()


def _send(f, msg):
    f.write(msg + "\n")
    f.flush()


def _status(board):
    if board.winner:
        return f"WIN:{board.winner}"
    if board.is_draw():
        return "DRAW"
    return f"TURN:{board.turn}"


def _broadcast_state(game):
    msg = f"STATE {game.board.render()} {_status(game.board)}"
    for f in game.conns.values():
        try:
            _send(f, msg)
        except (OSError, ValueError):
            pass
    _broadcast_spectators(game, msg)


def _broadcast_spectators(game, msg):
    with game.spectators_lock:
        for f in list(game.spectators):
            try:
                _send(f, msg)
            except (OSError, ValueError):
                game.spectators.remove(f)


def _handle_spectator(game, conn):
    f = conn.makefile("rw")
    with game.spectators_lock:
        game.spectators.append(f)
    try:
        _send(f, "WELCOME SPECTATOR")
        _send(f, f"STATE {game.board.render()} {_status(game.board)}")
        for _ in f:
            pass  # spectators don't send commands; just drain until they disconnect
    except (OSError, ValueError):
        pass
    finally:
        with game.spectators_lock:
            if f in game.spectators:
                game.spectators.remove(f)
        try:
            f.close()
        except OSError:
            pass
        try:
            conn.close()
        except OSError:
            pass


def _handle_client(game, symbol, sock, f):
    try:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if not parts or parts[0] != "MOVE" or len(parts) != 2:
                _send(f, "ERROR bad command")
                continue
            try:
                index = int(parts[1])
            except ValueError:
                _send(f, "ERROR bad index")
                continue
            with game.lock:
                try:
                    game.board.make_move(symbol, index)
                except InvalidMove as exc:
                    _send(f, f"ERROR {exc}")
                    continue
                _broadcast_state(game)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        if not game.board.is_over():
            other = "O" if symbol == "X" else "X"
            other_f = game.conns.get(other)
            if other_f is not None and other_f is not f:
                try:
                    _send(other_f, "OPPONENT_LEFT")
                except (OSError, ValueError):
                    pass
            _broadcast_spectators(game, "OPPONENT_LEFT")
        try:
            f.close()
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass


def serve(host, port, num_games=1, ready_event=None, bound_port_holder=None):
    """Accept pairs of players and run games sequentially until num_games complete.

    port=0 lets the OS pick a free port; pass bound_port_holder (a list) to
    read the actual bound port back out once ready_event is set. Used by both
    the CLI (fixed port) and tests (ephemeral port).
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(8)
    if bound_port_holder is not None:
        bound_port_holder.append(srv.getsockname()[1])
    if ready_event is not None:
        ready_event.set()

    # A single acceptor thread feeds every incoming connection into a queue.
    # The main loop pulls the first two per game off as players; anything
    # that arrives while a game already has both players becomes a spectator.
    conn_queue = queue.Queue()

    def accept_loop():
        while True:
            try:
                conn, _addr = srv.accept()
            except OSError:
                return
            conn_queue.put(conn)

    acceptor = threading.Thread(target=accept_loop, daemon=True)
    acceptor.start()

    try:
        for _ in range(num_games):
            game = Game()
            players = []
            for i, symbol in enumerate(("X", "O")):
                conn = conn_queue.get()
                f = conn.makefile("rw")
                game.conns[symbol] = f
                _send(f, f"WELCOME {symbol}")
                if i == 0:
                    _send(f, "WAITING")
                players.append((symbol, conn, f))

            _broadcast_state(game)

            threads = [
                threading.Thread(target=_handle_client, args=(game, symbol, conn, f), daemon=True)
                for symbol, conn, f in players
            ]
            for t in threads:
                t.start()

            spectator_stop = threading.Event()

            def spectator_intake():
                while not spectator_stop.is_set():
                    try:
                        conn = conn_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    threading.Thread(target=_handle_spectator, args=(game, conn), daemon=True).start()

            intake_thread = threading.Thread(target=spectator_intake, daemon=True)
            intake_thread.start()

            for t in threads:
                t.join()
            spectator_stop.set()
            intake_thread.join(timeout=1)
    finally:
        srv.close()
