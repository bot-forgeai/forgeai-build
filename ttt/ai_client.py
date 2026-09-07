"""Socket client that plays as an automated opponent, using ai.choose_move.

Speaks the same protocol as a human client (client.py): connects, reads
WELCOME to learn its symbol, then on each STATE where it's its turn,
computes and sends a MOVE. Lets a solo player run `ttt serve` +
`ttt join` + `ttt ai` to fill both seats without a second human.
"""
import socket

from .ai import choose_move


def run_ai_client(host, port, print_fn=print, match=False):
    """If match is True, keep playing across a --best-of match on the server
    instead of exiting after the first game (see SCORE/MATCH_OVER in
    server.py's protocol docstring)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    f = sock.makefile("rw")
    symbol = None
    try:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if parts[0] == "WELCOME" and len(parts) == 2:
                symbol = parts[1]
                print_fn(f"AI connected as {symbol}")
            elif parts[0] == "STATE" and len(parts) >= 3:
                cells, status = parts[1], parts[2]
                if symbol is not None and status == f"TURN:{symbol}":
                    index = choose_move(cells, symbol)
                    f.write(f"MOVE {index}\n")
                    f.flush()
                elif status.startswith("WIN:") or status == "DRAW":
                    print_fn(f"Game over: {status}")
                    if not match:
                        break
            elif parts[0] == "SCORE" and len(parts) == 3:
                print_fn(f"Score: X={parts[1]} O={parts[2]}")
            elif parts[0] == "MATCH_OVER" and len(parts) == 2:
                result = parts[1]
                print_fn("Match tied." if result == "TIE" else f"Match over: {result} wins")
                break
            elif parts[0] == "OPPONENT_LEFT":
                print_fn("Opponent left.")
                break
    except (OSError, ValueError):
        pass
    finally:
        f.close()
        sock.close()
