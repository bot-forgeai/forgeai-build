import argparse
import csv
import json
import sys
from importlib.metadata import version as _get_version, PackageNotFoundError

from .data import load_vitals, summarize
from .server import _load, make_server


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def parse_thresholds(specs):
    """Turn ["temp_c=70", "load1=4"] into {"temp_c": 70.0, "load1": 4.0}.

    "metric<value" is accepted too (breach when the value falls below);
    the value lands in the same dict, and parse_below_metrics names it.
    """
    thresholds = {}
    for spec in specs or []:
        name, _, value = _split_spec(spec)
        thresholds[name] = float(value)
    return thresholds


def parse_below_metrics(specs):
    """Names of metrics whose threshold was given as "metric<value"."""
    return [_split_spec(spec)[0] for spec in specs or [] if _split_spec(spec)[1] == "<"]


def _split_spec(spec):
    for op in ("<", "="):
        if op in spec:
            name, _, value = spec.partition(op)
            return name, op, value
    raise ValueError(f"--threshold expects metric=value or metric<value, got {spec!r}")


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
        type=threshold_spec,
        metavar="METRIC=VALUE",
        help="highlight a metric's chart when its latest value exceeds VALUE "
        "(repeatable, e.g. --threshold temp_c=70 --threshold load1=4); "
        "use METRIC<VALUE to flag a value falling below it "
        "(e.g. --threshold mem_available_mb<100)",
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
    parser.add_argument(
        "--last-days",
        type=positive_days,
        metavar="N",
        help="only chart records within N days of the newest timestamp "
        "(per-boot bar chart still covers the whole file)",
    )
    parser.add_argument(
        "--rate",
        action="append",
        default=[],
        metavar="METRIC",
        help="chart a cumulative counter (e.g. sectors_written) as a per-hour "
        "rate instead of a raw sawtooth; counter resets are dropped (repeatable)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="print a per-metric text table (n, min, mean, max, p95, trend/day, latest) and "
        "exit instead of serving; exits 1 if any --threshold is breached, "
        "so it can gate a script",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="with --summary, print the rows as a JSON array instead of a text "
        "table (same exit code), for scripts that parse the output",
    )
    return parser


def add_compare_means(rows, other_rows):
    """Set r["cmp_mean"] to the same metric's mean in other_rows (None if absent)."""
    other = {r["metric"]: r["mean"] for r in other_rows}
    for r in rows:
        r["cmp_mean"] = other.get(r["metric"])
    return rows


def format_summary(rows):
    """Render summarize() rows as an aligned text table; '!' marks a breach.

    Rows carrying "cmp_mean" (see add_compare_means) get two extra columns:
    the --compare file's mean and the difference (this minus that). Rows with a
    threshold also get breaches (samples past it, of n), the longest streak of
    them, and when the last one happened.
    """
    compare = any("cmp_mean" in r for r in rows)
    limits = any(r.get("breach_n") is not None for r in rows)
    header = ("metric", "n", "min", "mean", "max", "p95", "trend/d", "latest") + (("mean2", "diff") if compare else ()) \
        + (("breaches", "run", "last breach") if limits else ())
    body = []
    for r in rows:
        row = (r["metric"], str(r["n"]), f"{r['min']:.4g}", f"{r['mean']:.4g}",
               f"{r['max']:.4g}", f"{r['p95']:.4g}",
               "-" if r["trend_per_day"] is None else f"{r['trend_per_day']:+.3g}",
               f"{r['latest']:.4g}" + (" !" if r["breached"] else ""))
        if compare:
            c = r.get("cmp_mean")
            row += ("-", "-") if c is None else (f"{c:.4g}", f"{r['mean'] - c:+.4g}")
        if limits:
            b = r.get("breach_n")
            row += ("-", "-", "-") if b is None else (
                f"{b}/{r['n']}", str(r["breach_longest_run"]), r["last_breach"] or "-")
        body.append(row)
    widths = [max(len(row[i]) for row in [header] + body) for i in range(len(header))]
    lines = ["  ".join(c.ljust(w) if i == 0 else c.rjust(w) for i, (c, w) in enumerate(zip(row, widths)))
             for row in [header] + body]
    return "\n".join(lines)


def positive_days(text):
    """argparse type for --last-days: a number of days greater than zero."""
    try:
        days = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid number of days: {text!r}")
    if not days > 0:
        raise argparse.ArgumentTypeError(f"must be greater than 0, got {text}")
    return days


def threshold_spec(text):
    """argparse type for --threshold: METRIC=VALUE or METRIC<VALUE, VALUE numeric."""
    try:
        name, _, value = _split_spec(text)
        float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected METRIC=VALUE or METRIC<VALUE with a numeric VALUE, got {text!r}")
    if not name:
        raise argparse.ArgumentTypeError(f"missing metric name in {text!r}")
    return text


def unknown_metrics(names, known):
    """Names not among the CSV's metric columns, in the order given."""
    return [n for n in names if n not in known]


def csv_columns(path):
    """Header names of a CSV (empty if there is no header)."""
    with open(path, newline="") as f:
        return next(csv.reader(f), [])


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.json and not args.summary:
        parser.error("--json only applies together with --summary")

    thresholds = parse_thresholds(args.threshold)
    try:
        known, _ = load_vitals(args.csv)
    except (OSError, ValueError) as e:
        sys.exit(f"vitalsdash: cannot read {args.csv}: {e}")
    if args.compare:
        try:
            load_vitals(args.compare)
        except (OSError, ValueError) as e:
            sys.exit(f"vitalsdash: cannot read --compare {args.compare}: {e}")
    if args.bar_by is not None and args.bar_by not in csv_columns(args.csv):
        print(f"vitalsdash: warning: --bar-by {args.bar_by!r} matches no column in {args.csv} "
              f"(bar chart will not be drawn)", file=sys.stderr)
    for flag, names in (("--threshold", thresholds), ("--rate", args.rate)):
        for name in unknown_metrics(names, known):
            print(f"vitalsdash: warning: {flag} {name!r} matches no column in {args.csv} "
                  f"(columns: {', '.join(known)})", file=sys.stderr)
    if args.summary:
        metric_names, records = _load(args.csv, args.rate, args.last_days)
        rows = summarize(metric_names, records, thresholds, parse_below_metrics(args.threshold))
        if args.compare:
            names2, records2 = _load(args.compare, args.rate, args.last_days)
            add_compare_means(rows, summarize(names2, records2))
        print(json.dumps(rows, indent=2) if args.json else format_summary(rows))
        sys.exit(1 if any(r["breached"] for r in rows) else 0)
    server = make_server(
        args.csv,
        host=args.host,
        port=args.port,
        thresholds=thresholds,
        below=parse_below_metrics(args.threshold),
        compare_path=args.compare,
        group_by=args.bar_by,
        last_days=args.last_days,
        rate=args.rate,
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
