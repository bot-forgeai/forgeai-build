import argparse

from .server import make_server


def parse_thresholds(specs):
    """Turn ["temp_c=70", "load1=4"] into {"temp_c": 70.0, "load1": 4.0}."""
    thresholds = {}
    for spec in specs or []:
        if "=" not in spec:
            raise ValueError(f"--threshold expects metric=value, got {spec!r}")
        name, _, value = spec.partition("=")
        thresholds[name] = float(value)
    return thresholds


def main():
    parser = argparse.ArgumentParser(
        prog="vitalsdash",
        description="Serve a local dashboard for a timestamp+metrics CSV.",
    )
    parser.add_argument("csv", help="path to a vitals CSV (header: timestamp,<metric>,...)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument(
        "--threshold",
        action="append",
        metavar="METRIC=VALUE",
        help="highlight a metric's chart when its latest value exceeds VALUE "
        "(repeatable, e.g. --threshold temp_c=70 --threshold load1=4)",
    )
    args = parser.parse_args()

    thresholds = parse_thresholds(args.threshold)
    server = make_server(args.csv, host=args.host, port=args.port, thresholds=thresholds)
    print(f"vitalsdash serving {args.csv} at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
