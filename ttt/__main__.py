import argparse

from .ai_client import run_ai_client
from .client import run_client
from .server import serve
from .spectator_client import run_spectator_client


def build_arg_parser():
    parser = argparse.ArgumentParser(prog="ttt", description="Two-player tic-tac-toe over TCP")
    sub = parser.add_subparsers(dest="command", required=True)

    serve_p = sub.add_parser("serve", help="host a game and wait for two players to connect")
    serve_p.add_argument("--host", default="0.0.0.0", help="address to bind (LAN or localhost only)")
    serve_p.add_argument("--port", type=int, default=5050)
    serve_p.add_argument("--games", type=int, default=1, help="number of independent games to run before exiting")
    serve_p.add_argument(
        "--best-of", type=int, default=None,
        help="run a match: same two players replay until one reaches a majority of N wins "
             "(draws don't count and trigger a replay); overrides --games",
    )

    join_p = sub.add_parser("join", help="connect to a running game as a player")
    join_p.add_argument("host")
    join_p.add_argument("--port", type=int, default=5050)

    ai_p = sub.add_parser("ai", help="connect as an automated opponent (perfect-play minimax)")
    ai_p.add_argument("host")
    ai_p.add_argument("--port", type=int, default=5050)
    ai_p.add_argument("--match", action="store_true", help="keep playing across a --best-of match instead of exiting after one game")

    watch_p = sub.add_parser("watch", help="connect as a read-only spectator")
    watch_p.add_argument("host")
    watch_p.add_argument("--port", type=int, default=5050)

    return parser


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.command == "serve":
        print(f"Serving on {args.host}:{args.port}, waiting for players...")
        serve(args.host, args.port, num_games=args.games, best_of=args.best_of)
    elif args.command == "join":
        run_client(args.host, args.port)
    elif args.command == "ai":
        run_ai_client(args.host, args.port, match=args.match)
    elif args.command == "watch":
        run_spectator_client(args.host, args.port)


if __name__ == "__main__":
    main()
