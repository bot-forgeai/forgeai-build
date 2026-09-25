import argparse
import sys
from importlib.metadata import version as _get_version, PackageNotFoundError

from .interpreter import Interpreter, ToylangRuntimeError
from .lexer import ToylangSyntaxError, tokenize
from .parser import parse

OPEN_BRACKETS = {"(": ")", "{": "}", "[": "]"}
CLOSE_BRACKETS = {v: k for k, v in OPEN_BRACKETS.items()}


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def run_source(source, interpreter):
    program = parse(source)
    interpreter.run(program)


def cmd_run(args):
    with open(args.path) as f:
        source = f.read()
    interpreter = Interpreter()
    try:
        run_source(source, interpreter)
    except (ToylangSyntaxError, ToylangRuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def bracket_depth(source):
    """Net (/{/[ minus )/}/] depth, or None if source doesn't even tokenize
    yet (e.g. a string literal whose closing quote hasn't been typed)."""
    try:
        tokens = tokenize(source)
    except ToylangSyntaxError:
        return None
    depth = 0
    for tok in tokens:
        if tok.type in OPEN_BRACKETS:
            depth += 1
        elif tok.type in CLOSE_BRACKETS:
            depth -= 1
    return depth


def cmd_repl(args):
    print("toylang REPL (Ctrl-D to exit)")
    interpreter = Interpreter()
    buffer_lines = []
    while True:
        try:
            line = input("... " if buffer_lines else "> ")
        except EOFError:
            print()
            return 0
        if not line.strip() and not buffer_lines:
            continue
        buffer_lines.append(line)
        source_so_far = "\n".join(buffer_lines)
        depth = bracket_depth(source_so_far)
        if depth is None or depth > 0:
            # Unterminated string, or an open block/call: keep reading.
            continue
        # Let statements/blocks end themselves; bare expressions need a
        # trailing ';' the grammar requires but a REPL user won't type.
        stripped = source_so_far.rstrip()
        if depth == 0 and not stripped.endswith((";", "}")):
            stripped += ";"
        try:
            run_source(stripped, interpreter)
        except (ToylangSyntaxError, ToylangRuntimeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
        buffer_lines = []


def build_parser():
    parser = argparse.ArgumentParser(prog="toylang", description="Run or explore toylang scripts.")
    parser.add_argument("--version", action="version", version=_get_package_version())
    parser.add_argument("path", nargs="?", help="script file to run; omit for an interactive REPL")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.path:
        return cmd_run(args)
    return cmd_repl(args)


if __name__ == "__main__":
    sys.exit(main())
