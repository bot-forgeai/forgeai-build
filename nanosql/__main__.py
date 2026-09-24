import argparse
import sys
from importlib.metadata import version as _get_version, PackageNotFoundError

from .engine import NanosqlError
from .storage import load, save


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def _print_result(result):
    if result["kind"] == "ok":
        print(result["message"])
        return
    columns = result["columns"]
    rows = result["rows"]
    print("\t".join(columns))
    for row in rows:
        print("\t".join("" if row[c] is None else str(row[c]) for c in columns))
    print(f"({len(rows)} row(s))")


def cmd_exec(args):
    db = load(args.db)
    try:
        results = db.execute_script(args.sql)
    except NanosqlError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    for result in results:
        _print_result(result)
    if db.in_transaction():
        print(
            "error: script left a transaction open — add COMMIT or ROLLBACK",
            file=sys.stderr,
        )
        sys.exit(1)
    save(db, args.db)


def cmd_shell(args):
    db = load(args.db)
    print(f"nanosql shell on {args.db!r} — statements end with ';', 'quit' to exit")
    buffer = ""
    while True:
        try:
            prompt = "nanosql> " if not buffer else "     -> "
            line = input(prompt)
        except EOFError:
            break
        stripped = line.strip()
        if not buffer and stripped.lower() in ("quit", "exit"):
            break
        buffer += (" " if buffer else "") + line
        if ";" not in buffer:
            continue
        statement, _, buffer = buffer.partition(";")
        statement = statement.strip()
        if not statement:
            continue
        try:
            result = db.execute(statement)
        except NanosqlError as exc:
            print(f"error: {exc}")
            continue
        _print_result(result)
        if not db.in_transaction():
            save(db, args.db)
    if db.in_transaction():
        print("note: exiting with an open transaction — its changes were not saved")


def build_parser():
    parser = argparse.ArgumentParser(prog="nanosql", description="a tiny SQL database engine")
    parser.add_argument("--version", action="version", version=_get_package_version())
    sub = parser.add_subparsers(dest="command", required=True)

    p_exec = sub.add_parser("exec", help="run a single SQL statement against a database file")
    p_exec.add_argument("db", help="path to a nanosql JSON database file (created if missing)")
    p_exec.add_argument("sql", help="a single SQL statement")
    p_exec.set_defaults(func=cmd_exec)

    p_shell = sub.add_parser("shell", help="interactive SQL shell against a database file")
    p_shell.add_argument("db", help="path to a nanosql JSON database file (created if missing)")
    p_shell.set_defaults(func=cmd_shell)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
