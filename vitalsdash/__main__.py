import argparse
from importlib.metadata import version as _get_version, PackageNotFoundError

from .server import make_server


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def parse_thresholds(specs):
    """Turn ["temp_c=70", "load1=4"] into {"temp_c": 70.0, "load1": 4.0}."""
    thresholds = {}
    for spec in specs or []:
        if "=" not in spec:
            raise ValueError(f"--threshold expects metric=value, got {spec!r}")
        name, _, value = spec.partition("=")
        thresholds[name] = float(value)
    return thresholds


def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="vitalsdash",
        description="Serve a local dashboard for a timestamp+metrics CSV.",
    )
    parser.add_argument("--version", action="version", version=_get_package_version())
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
    parser.add_argument(
        "--compare",
        metavar="CSV",
        help="a second vitals CSV to render side by side with the first, "
        "per shared metric (e.g. compare two boots or two machines)",
    )
    parser.add_argument(
        "--bar-by",
        metavar="COLUMN",
        help="explicitly group the bar chart by this column instead of "
        "auto-detecting it; needed when the CSV has more than one "
        "non-numeric column so auto-detect can't pick one unambiguously",
    )
    return parser


def main():
    args = build_arg_parser().parse_args()

    thresholds = parse_thresholds(args.threshold)
    server = make_server(
        args.csv,
        host=args.host,
        port=args.port,
        thresholds=thresholds,
        compare_path=args.compare,
        group_by=args.bar_by,
    )
    print(f"vitalsdash serving {args.csv} at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
