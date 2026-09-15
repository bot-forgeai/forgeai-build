"""Socket client that plays as an automated opponent, using ai.choose_move.

Speaks the same protocol as a human client (client.py): connects, reads
WELCOME to learn its color, then on each STATE where it's its turn (or
it's in check on its turn), reconstructs the board from the fen field and
computes+sends a MOVE. Lets a solo player run `chesslite serve` +
`chesslite join` + `chesslite ai` to fill both seats without a second
human.
"""
import socket

from .ai import choose_move
from .fen import from_fen
from .game import Game
from .server import from_wire


def run_ai_client(host, port, depth=2, print_fn=print):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    f = sock.makefile("rw")
    color = None
    try:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if parts[0] == "WELCOME" and len(parts) == 2:
                color = parts[1]
                print_fn(f"AI connected as {color}")
            elif parts[0] == "STATE" and len(parts) >= 3:
                status = parts[2]
                if color is not None and status in (f"TURN:{color}", f"CHECK:{color}"):
                    board = from_fen(from_wire(parts[1]))
                    move = choose_move(board, color, depth=depth)
                    if move is not None:
                        f.write(f"MOVE {Game(board).move_str(move)}\n")
                        f.flush()
                elif status.startswith("CHECKMATE") or status in ("STALEMATE", "DRAW"):
                    print_fn(f"Game over: {status}")
                    break
            elif parts[0] == "OPPONENT_LEFT":
                print_fn("Opponent left.")
                break
            elif parts[0] == "ERROR":
                print_fn(" ".join(parts))
    except (OSError, ValueError):
        pass
    finally:
        f.close()
        sock.close()
