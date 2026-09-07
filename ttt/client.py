"""Interactive terminal client for the ttt server."""
import socket
import threading


def _format_state(line):
    parts = line.split()
    if len(parts) >= 2 and parts[0] == "STATE":
        cells = parts[1]
        status = parts[2] if len(parts) > 2 else ""
        rows = [cells[i:i + 3] for i in range(0, 9, 3)]
        grid = "\n".join(" ".join(row) for row in rows)
        return f"{grid}\n{status}"
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
    print_fn("Connected. Enter a cell number 0-8 to move, or 'quit' to exit.")
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
