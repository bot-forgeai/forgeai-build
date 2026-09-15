import argparse
import sys

from .ai import choose_move
from .board import color_of
from .game import Game, IllegalMoveError


def build_arg_parser():
    parser = argparse.ArgumentParser(prog="chesslite", description="A small chess engine")
    sub = parser.add_subparsers(dest="command", required=True)

    play_p = sub.add_parser("play", help="play an interactive game")
    play_p.add_argument(
        "--ai", choices=["w", "b"], default=None,
        help="let the engine play this color instead of a second human",
    )
    play_p.add_argument("--depth", type=int, default=2, help="AI search depth (default: 2)")

    return parser


def _print_board(game: Game):
    print(game.board.render())
    turn = "White" if game.to_move == "w" else "Black"
    suffix = " (in check)" if game.in_check() else ""
    print(f"{turn} to move{suffix}")


def run_play(ai_color=None, depth=2):
    game = Game()
    while True:
        _print_board(game)
        result = game.result()
        if result == "checkmate":
            winner = "Black" if game.to_move == "w" else "White"
            print(f"Checkmate. {winner} wins.")
            return 0
        if result == "stalemate":
            print("Stalemate. Draw.")
            return 0
        if result == "draw":
            print("Draw.")
            return 0

        if game.to_move == ai_color:
            move = choose_move(game.board, ai_color, depth=depth)
            game.make_move(move)
            print(f"AI plays {game.move_str(move)}")
            continue

        try:
            text = input(f"{'White' if game.to_move == 'w' else 'Black'}'s move: ")
        except EOFError:
            print()
            return 0
        if not text.strip():
            continue
        try:
            game.make_move(text)
        except IllegalMoveError as exc:
            print(f"error: {exc}", file=sys.stderr)


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.command == "play":
        return run_play(ai_color=args.ai, depth=args.depth)
    return 1


if __name__ == "__main__":
    sys.exit(main())
