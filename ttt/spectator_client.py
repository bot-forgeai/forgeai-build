"""Read-only terminal client that watches a game without playing."""
import socket

from .client import _format_state


def run_spectator_client(host, port, print_fn=print):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    f = sock.makefile("rw")
    try:
        print_fn("Watching. Press Ctrl+C to stop.")
        for line in f:
            print_fn(_format_state(line.rstrip("\n")))
        print_fn("[disconnected]")
    finally:
        f.close()
        sock.close()
