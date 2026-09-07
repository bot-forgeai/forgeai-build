"""Socket client that plays as an automated opponent, using ai.choose_move.

Speaks the same protocol as a human client (client.py): connects, reads
WELCOME to learn its symbol, then on each STATE where it's its turn,
computes and sends a MOVE. Lets a solo player run `ttt serve` +
`ttt join` + `ttt ai` to fill both seats without a second human.
"""
import socket

from .ai import choose_move


def run_ai_client(host, port, print_fn=print):
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
                    break
            elif parts[0] == "OPPONENT_LEFT":
                print_fn("Opponent left.")
                break
    except (OSError, ValueError):
        pass
    finally:
        f.close()
        sock.close()
