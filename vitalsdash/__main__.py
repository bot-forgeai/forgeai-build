import argparse

from .server import make_server


def main():
    parser = argparse.ArgumentParser(
        prog="vitalsdash",
        description="Serve a local dashboard for a timestamp+metrics CSV.",
    )
    parser.add_argument("csv", help="path to a vitals CSV (header: timestamp,<metric>,...)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()

    server = make_server(args.csv, host=args.host, port=args.port)
    print(f"vitalsdash serving {args.csv} at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
