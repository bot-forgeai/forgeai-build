"""CLI for huffc: a small Huffman-coding file compressor."""

import argparse
import os
import sys
from importlib.metadata import version as _get_version, PackageNotFoundError

from .archive import ArchiveError, pack_archive, unpack_archive, _collect_entries
from .format import FormatError, compress, decompress


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def _read_input(path):
    if path == "-":
        return sys.stdin.buffer.read()
    with open(path, "rb") as f:
        return f.read()


def _write_output(path, data):
    if path == "-":
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    else:
        with open(path, "wb") as f:
            f.write(data)


def cmd_compress(args):
    data = _read_input(args.input)
    blob = compress(data)
    _write_output(args.output, blob)
    if not args.quiet and args.output != "-":
        orig = len(data)
        comp = len(blob)
        ratio = (comp / orig) if orig else 0.0
        print(f"{args.input}: {orig} -> {comp} bytes ({ratio:.2%} of original)")


def cmd_decompress(args):
    blob = _read_input(args.input)
    try:
        data = decompress(blob)
    except FormatError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    _write_output(args.output, data)
    if not args.quiet and args.output != "-":
        print(f"{args.input}: {len(blob)} -> {len(data)} bytes")
    return 0


def cmd_stats(args):
    data = _read_input(args.input)
    blob = compress(data)
    orig = len(data)
    comp = len(blob)
    ratio = (comp / orig) if orig else 0.0
    print(f"original:   {orig} bytes")
    print(f"compressed: {comp} bytes")
    print(f"ratio:      {ratio:.2%}")
    return 0


def cmd_archive(args):
    blob = pack_archive(args.inputs)
    with open(args.output, "wb") as f:
        f.write(blob)
    if not args.quiet:
        entries = _collect_entries(args.inputs)
        total_in = sum(os.path.getsize(p) for p, _name in entries)
        print(f"{args.output}: {len(entries)} file(s), {total_in} -> {len(blob)} bytes")
    return 0


def cmd_extract(args):
    with open(args.archive, "rb") as f:
        blob = f.read()
    try:
        entries = unpack_archive(blob)
    except (ArchiveError, FormatError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    for name, data in entries:
        dest = os.path.join(outdir, *name.split("/"))
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        if not args.quiet:
            print(f"{name}: {len(data)} bytes -> {dest}")
    return 0


def cmd_list(args):
    with open(args.archive, "rb") as f:
        blob = f.read()
    try:
        entries = unpack_archive(blob)
    except (ArchiveError, FormatError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    for name, data in entries:
        print(f"{name}\t{len(data)} bytes")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="huffc", description="Huffman-coding file compressor")
    parser.add_argument("--version", action="version", version=_get_package_version())
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

    a = sub.add_parser("archive", help="compress multiple files (or directories) into one archive")
    a.add_argument("output")
    a.add_argument("inputs", nargs="+", help="files and/or directories to archive")
    a.add_argument("-q", "--quiet", action="store_true")
    a.set_defaults(func=cmd_archive)

    e = sub.add_parser("extract", help="extract every file from an archive")
    e.add_argument("archive")
    e.add_argument("-o", "--outdir", default=".")
    e.add_argument("-q", "--quiet", action="store_true")
    e.set_defaults(func=cmd_extract)

    ls = sub.add_parser("list", help="list files in an archive")
    ls.add_argument("archive")
    ls.set_defaults(func=cmd_list)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
