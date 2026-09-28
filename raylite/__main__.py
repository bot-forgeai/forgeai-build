"""raylite CLI: render a JSON scene description to a PPM image."""

from __future__ import annotations

import argparse
import sys
import time

from raylite import __version__
from raylite.png import write_png
from raylite.ppm import write_ppm
from raylite.render import render
from raylite.scene import SceneError, load_scene


def cmd_render(args: argparse.Namespace) -> int:
    try:
        scene = load_scene(args.scene)
    except (SceneError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.width <= 0 or args.height <= 0:
        print("error: width and height must be positive", file=sys.stderr)
        return 1
    if args.samples <= 0:
        print("error: samples must be positive", file=sys.stderr)
        return 1
    if args.workers <= 0:
        print("error: workers must be positive", file=sys.stderr)
        return 1

    fmt = args.format
    if fmt is None:
        fmt = "png" if args.output.lower().endswith(".png") else "ppm"

    start = time.time()
    pixels = render(
        scene,
        args.width,
        args.height,
        samples_per_pixel=args.samples,
        workers=args.workers,
        seed=args.seed,
    )
    elapsed = time.time() - start

    if fmt == "png":
        write_png(args.output, pixels)
    else:
        write_ppm(args.output, pixels)
    print(f"rendered {args.width}x{args.height} ({args.samples} spp) to {args.output} ({fmt}) in {elapsed:.2f}s")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="raylite", description="A small CPU ray tracer.")
    parser.add_argument("--version", action="version", version=f"raylite {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser("render", help="render a JSON scene to a PPM image")
    render_parser.add_argument("scene", help="path to a JSON scene description")
    render_parser.add_argument("output", help="path to write the output .ppm image")
    render_parser.add_argument("--width", type=int, default=400)
    render_parser.add_argument("--height", type=int, default=300)
    render_parser.add_argument(
        "--samples", type=int, default=1, help="samples per pixel (anti-aliasing; higher is slower/smoother)"
    )
    render_parser.add_argument(
        "--format",
        choices=["ppm", "png"],
        default=None,
        help="output image format; defaults to inferring from the output filename's extension (.png -> png, else ppm)",
    )
    render_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="number of worker processes to render rows in parallel (default 1, sequential)",
    )
    render_parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for reproducible renders (only used when --workers > 1; a single-worker render "
        "already uses a fresh internal RNG unless a caller supplies one)",
    )
    render_parser.set_defaults(func=cmd_render)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
