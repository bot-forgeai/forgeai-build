import argparse
import sys
from importlib.metadata import version as _get_version, PackageNotFoundError

from .ai import choose_move
from .ai_client import run_ai_client
from .board import color_of
from .client import run_client
from .game import Game, IllegalMoveError
from .server import serve


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def build_arg_parser():
    parser = argparse.ArgumentParser(prog="chesslite", description="A small chess engine")
    parser.add_argument("--version", action="version", version=_get_package_version())
    sub = parser.add_subparsers(dest="command", required=True)

    play_p = sub.add_parser("play", help="play an interactive local game")
    play_p.add_argument(
        "--ai", choices=["w", "b"], default=None,
        help="let the engine play this color instead of a second human",
    )
    play_p.add_argument("--depth", type=int, default=2, help="AI search depth (default: 2)")
    play_p.add_argument("--pgn", default=None, help="write the finished game's movetext to this PGN file")
    play_p.add_argument(
        "--load-pgn", default=None,
        help="replay this PGN file's movetext before play continues from that position",
    )

    serve_p = sub.add_parser("serve", help="host a game over TCP and wait for two players to connect")
    serve_p.add_argument("--host", default="0.0.0.0", help="address to bind (LAN or localhost only)")
    serve_p.add_argument("--port", type=int, default=5060)

    join_p = sub.add_parser("join", help="connect to a running networked game as a player")
    join_p.add_argument("host")
    join_p.add_argument("--port", type=int, default=5060)

    ai_p = sub.add_parser("ai", help="connect to a running networked game as an automated opponent")
    ai_p.add_argument("host")
    ai_p.add_argument("--port", type=int, default=5060)
    ai_p.add_argument("--depth", type=int, default=2, help="AI search depth (default: 2)")

    return parser


def _print_board(game: Game):
    print(game.board.render())
    turn = "White" if game.to_move == "w" else "Black"
    suffix = " (in check)" if game.in_check() else ""
    print(f"{turn} to move{suffix}")


def _write_pgn(game: Game, path: str, result: str):
    with open(path, "w") as f:
        f.write(game.to_pgn(result) + "\n")


def run_play(ai_color=None, depth=2, pgn_path=None, load_pgn_path=None):
    if load_pgn_path:
        with open(load_pgn_path) as f:
            try:
                game = Game.from_pgn(f.read())
            except IllegalMoveError as exc:
                print(f"error: bad PGN in {load_pgn_path}: {exc}", file=sys.stderr)
                return 1
    else:
        game = Game()
    while True:
        _print_board(game)
        result = game.result()
        if result == "checkmate":
            winner = "Black" if game.to_move == "w" else "White"
            print(f"Checkmate. {winner} wins.")
            if pgn_path:
                _write_pgn(game, pgn_path, "0-1" if winner == "Black" else "1-0")
            return 0
        if result == "stalemate":
            print("Stalemate. Draw.")
            if pgn_path:
                _write_pgn(game, pgn_path, "1/2-1/2")
            return 0
        if result == "draw":
            print("Draw.")
            if pgn_path:
                _write_pgn(game, pgn_path, "1/2-1/2")
            return 0

        if game.to_move == ai_color:
            move = choose_move(game.board, ai_color, depth=depth)
            san = game.san(move)
            game.make_move(move)
            print(f"AI plays {san} ({game.move_str(move)})")
            continue

        try:
            text = input(f"{'White' if game.to_move == 'w' else 'Black'}'s move: ")
        except EOFError:
            print()
            if pgn_path:
                _write_pgn(game, pgn_path, "*")
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
        return run_play(
            ai_color=args.ai, depth=args.depth, pgn_path=args.pgn,
            load_pgn_path=args.load_pgn,
        )
    if args.command == "serve":
        print(f"Serving on {args.host}:{args.port}, waiting for players...")
        serve(args.host, args.port)
        return 0
    if args.command == "join":
        run_client(args.host, args.port)
        return 0
    if args.command == "ai":
        run_ai_client(args.host, args.port, depth=args.depth)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
