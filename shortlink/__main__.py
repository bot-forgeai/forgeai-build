import argparse

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


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    server = make_server(args.db, host=args.host, port=args.port)
    print(f"shortlink serving on http://{args.host}:{args.port} (db: {args.db})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
