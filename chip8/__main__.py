import argparse
import sys
from importlib.metadata import version as _get_version, PackageNotFoundError

from .cpu import CPU, Chip8Error
from .render import to_ascii

CYCLES_PER_FRAME = 10  # a rough approximation of real CHIP-8 timing (~600Hz CPU, 60Hz timers)

QUIRK_PROFILES = {
    "modern": {"shift_quirk": True, "load_store_quirk": True},
    "classic": {"shift_quirk": False, "load_store_quirk": False},
}


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def cmd_run(args):
    with open(args.rom, "rb") as f:
        data = f.read()
    cpu = CPU(**QUIRK_PROFILES[args.quirks])
    try:
        cpu.load_rom(data)
    except Chip8Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    frames = args.frames
    try:
        for _ in range(frames):
            for _ in range(CYCLES_PER_FRAME):
                cpu.step()
            cpu.tick_timers()
    except Chip8Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(to_ascii(cpu.display))
    return 0


def cmd_play(args):
    from .interactive import run_interactive
    from .terminal import RawMode, read_available_keys, clear_and_render, bell

    with open(args.rom, "rb") as f:
        data = f.read()
    cpu = CPU(**QUIRK_PROFILES[args.quirks])
    try:
        cpu.load_rom(data)
    except Chip8Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        with RawMode():
            run_interactive(
                cpu, read_available_keys, clear_and_render, bell,
                frame_limit=args.frames,
            )
    except Chip8Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    return 0


def cmd_disasm(args):
    from .disasm import disassemble_rom

    with open(args.rom, "rb") as f:
        data = f.read()
    for addr, text in disassemble_rom(data):
        print(f"{addr:04X}: {text}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="chip8", description="A CHIP-8 emulator.")
    parser.add_argument("--version", action="version", version=f"chip8 {_get_package_version()}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_p = subparsers.add_parser("run", help="run a ROM headlessly and print the final display as ASCII")
    run_p.add_argument("rom")
    run_p.add_argument("--frames", type=int, default=60, help="number of 60Hz frames to run before printing the display (default: 60)")
    run_p.add_argument("--quirks", choices=sorted(QUIRK_PROFILES), default="modern",
                        help="interpreter quirk profile: 'modern' (default) or 'classic' (original COSMAC VIP 8XY6/8XYE/FX55/FX65 semantics)")
    run_p.set_defaults(func=cmd_run)

    play_p = subparsers.add_parser("play", help="run a ROM live in the terminal with real-time keyboard input")
    play_p.add_argument("rom")
    play_p.add_argument("--frames", type=int, default=None, help="stop after this many 60Hz frames (default: run until ESC or Ctrl-C)")
    play_p.add_argument("--quirks", choices=sorted(QUIRK_PROFILES), default="modern",
                         help="interpreter quirk profile: 'modern' (default) or 'classic' (original COSMAC VIP 8XY6/8XYE/FX55/FX65 semantics)")
    play_p.set_defaults(func=cmd_play)

    disasm_p = subparsers.add_parser("disasm", help="disassemble a ROM's opcodes")
    disasm_p.add_argument("rom")
    disasm_p.set_defaults(func=cmd_disasm)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
