import argparse
import json
import signal
import sys

from procman.config import ConfigError, load_config
from procman.supervisor import Supervisor


def cmd_run(args):
    try:
        services = load_config(args.config)
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    sup = Supervisor(services, log_dir=args.log_dir, status_path=args.status)

    stopped = {"flag": False}

    def handle_signal(signum, frame):
        stopped["flag"] = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    sup.run_forever(
        poll_interval=args.interval,
        stop_flag=lambda: stopped["flag"],
        max_iterations=args.max_iterations,
    )
    return 0


def cmd_status(args):
    try:
        with open(args.status_file) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"error: status file not found: {args.status_file}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"error: invalid status file: {e}", file=sys.stderr)
        return 1

    name_w = max([len(n) for n in data] + [4])
    print(f"{'NAME'.ljust(name_w)}  STATE    PID      RESTARTS  LAST_EXIT")
    for name, s in data.items():
        state = "running" if s["running"] else "stopped"
        pid = str(s["pid"]) if s["pid"] is not None else "-"
        last_exit = str(s["last_exit_code"]) if s["last_exit_code"] is not None else "-"
        print(f"{name.ljust(name_w)}  {state.ljust(7)}  {pid.ljust(7)}  {str(s['restarts']).ljust(8)}  {last_exit}")
    return 0


def cmd_validate(args):
    try:
        services = load_config(args.config)
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"ok: {len(services)} service(s) defined")
    for s in services:
        print(f"  - {s.name}: {' '.join(s.command)}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="procman", description="A small process supervisor.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="start and supervise all services in a config file")
    p_run.add_argument("config")
    p_run.add_argument("--log-dir", default="procman-logs")
    p_run.add_argument("--status", default=None, help="path to write a live JSON status file")
    p_run.add_argument("--interval", type=float, default=1.0, help="poll interval in seconds")
    p_run.add_argument("--max-iterations", type=int, default=None, help="stop after N poll iterations (mainly for tests)")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="print a status file written by 'run'")
    p_status.add_argument("status_file")
    p_status.set_defaults(func=cmd_status)

    p_validate = sub.add_parser("validate", help="check a config file without running anything")
    p_validate.add_argument("config")
    p_validate.set_defaults(func=cmd_validate)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
