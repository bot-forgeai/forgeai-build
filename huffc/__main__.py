"""CLI for huffc: a small Huffman-coding file compressor."""

import argparse
import sys

from .format import FormatError, compress, decompress


def cmd_compress(args):
    with open(args.input, "rb") as f:
        data = f.read()
    blob = compress(data)
    with open(args.output, "wb") as f:
        f.write(blob)
    if not args.quiet:
        orig = len(data)
        comp = len(blob)
        ratio = (comp / orig) if orig else 0.0
        print(f"{args.input}: {orig} -> {comp} bytes ({ratio:.2%} of original)")


def cmd_decompress(args):
    with open(args.input, "rb") as f:
        blob = f.read()
    try:
        data = decompress(blob)
    except FormatError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    with open(args.output, "wb") as f:
        f.write(data)
    if not args.quiet:
        print(f"{args.input}: {len(blob)} -> {len(data)} bytes")
    return 0


def cmd_stats(args):
    with open(args.input, "rb") as f:
        data = f.read()
    blob = compress(data)
    orig = len(data)
    comp = len(blob)
    ratio = (comp / orig) if orig else 0.0
    print(f"original:   {orig} bytes")
    print(f"compressed: {comp} bytes")
    print(f"ratio:      {ratio:.2%}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="huffc", description="Huffman-coding file compressor")
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("compress", help="compress a file")
    c.add_argument("input")
    c.add_argument("output")
    c.add_argument("-q", "--quiet", action="store_true")
    c.set_defaults(func=cmd_compress)

    d = sub.add_parser("decompress", help="decompress a file")
    d.add_argument("input")
    d.add_argument("output")
    d.add_argument("-q", "--quiet", action="store_true")
    d.set_defaults(func=cmd_decompress)

    s = sub.add_parser("stats", help="show compression stats without writing an output file")
    s.add_argument("input")
    s.set_defaults(func=cmd_stats)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
