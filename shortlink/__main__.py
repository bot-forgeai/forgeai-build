import argparse
import socket

from .server import make_server


def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="shortlink",
        description="A small URL shortener with SQLite-backed click tracking.",
    )
    parser.add_argument("--db", default="shortlink.db", help="path to the SQLite database file")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    return parser


def get_lan_ip():
    """Best-effort local LAN IP, for printing a reachable URL when bound to 0.0.0.0.

    Opens a UDP socket to a public address without sending any data --
    the OS picks the outbound interface, which reveals this host's own
    LAN-facing IP. Falls back to "127.0.0.1" if there's no route (e.g.
    offline).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    server = make_server(args.db, host=args.host, port=args.port)
    print(f"shortlink serving on http://{args.host}:{args.port} (db: {args.db})")
    if args.host in ("0.0.0.0", "::"):
        print(f"  reachable on the LAN at http://{get_lan_ip()}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
