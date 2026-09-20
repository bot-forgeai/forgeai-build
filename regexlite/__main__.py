import argparse
import sys
from importlib.metadata import version as _get_version, PackageNotFoundError

from .matcher import Pattern
from .parser import RegexSyntaxError


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def _print_groups(m):
    for i, g in enumerate(m.groups(), start=1):
        print(f"  group {i}: {g!r} span={m.span(i)}")


def cmd_match(args):
    pat = Pattern(args.pattern)
    m = pat.fullmatch(args.string) if args.full else pat.match(args.string)
    if m is None:
        print("no match")
        return 1
    print(f"match: {m.group()!r} span={m.span()}")
    _print_groups(m)
    return 0


def cmd_search(args):
    pat = Pattern(args.pattern)
    m = pat.search(args.string)
    if m is None:
        print("no match")
        return 1
    print(f"match: {m.group()!r} span={m.span()}")
    _print_groups(m)
    return 0


def cmd_findall(args):
    pat = Pattern(args.pattern)
    matches = pat.findall(args.string)
    if not matches:
        print("no matches")
        return 1
    for m in matches:
        print(f"{m.group()!r} span={m.span()}")
    return 0


def cmd_grep(args):
    pat = Pattern(args.pattern)
    found = False
    try:
        with open(args.file, "r") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.rstrip("\n")
                if pat.search(line) is not None:
                    found = True
                    print(f"{lineno}:{line}")
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0 if found else 1


def build_parser():
    parser = argparse.ArgumentParser(prog="regexlite")
    parser.add_argument("--version", action="version", version=_get_package_version())
    sub = parser.add_subparsers(dest="command", required=True)

    p_match = sub.add_parser("match", help="match pattern against string, anchored at the start")
    p_match.add_argument("pattern")
    p_match.add_argument("string")
    p_match.add_argument("--full", action="store_true", help="require the whole string to match")
    p_match.set_defaults(func=cmd_match)

    p_search = sub.add_parser("search", help="find the first match anywhere in string")
    p_search.add_argument("pattern")
    p_search.add_argument("string")
    p_search.set_defaults(func=cmd_search)

    p_findall = sub.add_parser("findall", help="find all non-overlapping matches in string")
    p_findall.add_argument("pattern")
    p_findall.add_argument("string")
    p_findall.set_defaults(func=cmd_findall)

    p_grep = sub.add_parser("grep", help="print lines of a file matching pattern")
    p_grep.add_argument("pattern")
    p_grep.add_argument("file")
    p_grep.set_defaults(func=cmd_grep)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RegexSyntaxError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
