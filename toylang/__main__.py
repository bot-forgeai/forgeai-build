import argparse
import sys

from .interpreter import Interpreter, ToylangRuntimeError
from .lexer import ToylangSyntaxError
from .parser import parse


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


def cmd_repl(args):
    print("toylang REPL (Ctrl-D to exit)")
    interpreter = Interpreter()
    while True:
        try:
            line = input("> ")
        except EOFError:
            print()
            return 0
        if not line.strip():
            continue
        # Let statements/blocks end themselves; bare expressions need a
        # trailing ';' the grammar requires but a REPL user won't type.
        stripped = line.rstrip()
        if not stripped.endswith((";", "}")):
            stripped += ";"
        try:
            run_source(stripped, interpreter)
        except (ToylangSyntaxError, ToylangRuntimeError) as exc:
            print(f"error: {exc}", file=sys.stderr)


def build_parser():
    parser = argparse.ArgumentParser(prog="toylang", description="Run or explore toylang scripts.")
    parser.add_argument("path", nargs="?", help="script file to run; omit for an interactive REPL")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.path:
        return cmd_run(args)
    return cmd_repl(args)


if __name__ == "__main__":
    sys.exit(main())
