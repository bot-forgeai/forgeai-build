"""Command-line interface for quest: play a text adventure, with save/load."""
import argparse
import os
import sys

from .engine import describe_room, process_command
from .save import load_game, save_game
from .world import GameState, WorldError, load_world

DEFAULT_WORLD = os.path.join(os.path.dirname(__file__), "games", "sample.json")


def run_game(state, world_path, input_fn=input, print_fn=print, default_save_path=None):
    """Drive the interactive loop. Returns 'won', 'quit', or 'eof'."""
    print_fn(describe_room(state))
    while True:
        try:
            line = input_fn("> ")
        except EOFError:
            return "eof"

        stripped = line.strip()
        if stripped.lower() == "save" or stripped.lower().startswith("save "):
            parts = stripped.split(maxsplit=1)
            target = parts[1] if len(parts) > 1 else default_save_path
            if not target:
                print_fn("Save where? Usage: save <path>")
                continue
            save_game(state, target, world_path)
            print_fn(f"Game saved to {target}")
            continue

        result = process_command(state, line)
        if result.message:
            print_fn(result.message)
        if result.won:
            ending = state.flags.get("ending")
            print_fn(f"*** You win! ({ending}) ***" if ending else "*** You win! ***")
            return "won"
        if result.quit:
            return "quit"


def build_arg_parser():
    parser = argparse.ArgumentParser(prog="quest", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    play_p = sub.add_parser("play", help="play a game interactively")
    play_p.add_argument("--world", default=DEFAULT_WORLD, help="path to a world JSON file")
    play_p.add_argument("--load", default=None, help="load a saved game instead of starting fresh")
    play_p.add_argument("--save", default=None, help="default path used by the in-game 'save' command")

    return parser


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "play":
        try:
            if args.load:
                state, world_path = load_game(args.load)
                world_path = world_path or args.world
            else:
                world = load_world(args.world)
                state = GameState(world)
                world_path = args.world
        except (WorldError, FileNotFoundError, OSError) as exc:
            print(f"quest: {exc}", file=sys.stderr)
            return 1

        outcome = run_game(state, world_path, default_save_path=args.save)
        return 0 if outcome in ("won", "quit", "eof") else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
