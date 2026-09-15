"""Interactive terminal client for the chesslite server."""
import socket
import threading

from .fen import from_fen
from .server import from_wire


def _format_state(line):
    parts = line.split()
    if len(parts) >= 3 and parts[0] == "STATE":
        board = from_fen(from_wire(parts[1]))
        status = parts[2]
        return f"{board.render()}\n{status}"
    return line


def _listen(f, print_fn):
    for line in f:
        print_fn(_format_state(line.rstrip("\n")))
    print_fn("[disconnected]")


def run_client(host, port, input_fn=input, print_fn=print):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    f = sock.makefile("rw")
    listener = threading.Thread(target=_listen, args=(f, print_fn), daemon=True)
    listener.start()
    print_fn("Connected. Enter a move like e2e4 (e7e8q for promotion), or 'quit' to exit.")
    try:
        while True:
            try:
                line = input_fn("> ")
            except EOFError:
                break
            line = line.strip()
            if line in ("quit", "exit"):
                break
            if not line:
                continue
            try:
                f.write(f"MOVE {line}\n")
                f.flush()
            except OSError:
                break
    finally:
        f.close()
        sock.close()
