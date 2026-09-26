import argparse
import json
import os
import signal
import sys
import time
from importlib.metadata import version as _get_version, PackageNotFoundError

from procman.config import ConfigError, load_config
from procman.supervisor import StartupError, Supervisor


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def cmd_run(args):
    try:
        services = load_config(args.config)
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    sup = Supervisor(services, log_dir=args.log_dir, status_path=args.status,
                      default_max_log_bytes=args.max_log_bytes)

    stopped = {"flag": False}

    def handle_signal(signum, frame):
        stopped["flag"] = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if args.pid_file:
        with open(args.pid_file, "w") as f:
            f.write(str(os.getpid()))

    try:
        sup.run_forever(
            poll_interval=args.interval,
            stop_flag=lambda: stopped["flag"],
            max_iterations=args.max_iterations,
        )
    except StartupError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        if args.pid_file:
            try:
                os.remove(args.pid_file)
            except OSError:
                pass
    return 0


def cmd_stop(args):
    try:
        with open(args.pid_file) as f:
            content = f.read().strip()
    except FileNotFoundError:
        print(f"error: pid file not found: {args.pid_file}", file=sys.stderr)
        return 1
    try:
        pid = int(content)
    except ValueError:
        print(f"error: invalid pid file: {args.pid_file}", file=sys.stderr)
        return 1

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        print(f"error: no running process with pid {pid}", file=sys.stderr)
        return 1
    except PermissionError:
        print(f"error: permission denied signaling pid {pid}", file=sys.stderr)
        return 1

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        try:
            # If the target happens to be our own child (e.g. spawned
            # via subprocess.Popen in the same script), it lingers as
            # a zombie after exiting until reaped -- and os.kill(pid, 0)
            # succeeds on a zombie, since its pid is still allocated.
            # Reap it here so liveness below reflects reality either way.
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass  # not our child; fall through to the liveness check
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            print(f"stopped (pid {pid})")
            return 0
        time.sleep(0.1)
    print(f"error: process {pid} did not exit within {args.timeout}s", file=sys.stderr)
    return 1


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
        deps = f" (depends_on: {', '.join(s.depends_on)})" if s.depends_on else ""
        ready = f" (ready_check: {s.ready_check['type']})" if s.ready_check else ""
        max_log = f" (max_log_bytes: {s.max_log_bytes})" if s.max_log_bytes else ""
        print(f"  - {s.name}: {' '.join(s.command)}{deps}{ready}{max_log}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="procman", description="A small process supervisor.")
    p.add_argument("--version", action="version", version=_get_package_version())
    sub = p.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="start and supervise all services in a config file")
    p_run.add_argument("config")
    p_run.add_argument("--log-dir", default="procman-logs")
    p_run.add_argument("--status", default=None, help="path to write a live JSON status file")
    p_run.add_argument("--interval", type=float, default=1.0, help="poll interval in seconds")
    p_run.add_argument("--max-iterations", type=int, default=None, help="stop after N poll iterations (mainly for tests)")
    p_run.add_argument("--max-log-bytes", type=int, default=None,
                        help="rotate a service's log to a .1 backup once it reaches this size (checked at every spawn); "
                             "a service's own 'max_log_bytes' config value overrides this default")
    p_run.add_argument("--pid-file", default=None,
                        help="write this process's pid here on start, and remove it on clean exit; "
                             "lets 'procman stop' find and stop this run from another terminal or script")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="print a status file written by 'run'")
    p_status.add_argument("status_file")
    p_status.set_defaults(func=cmd_status)

    p_stop = sub.add_parser("stop", help="send SIGTERM to a 'procman run' process via its --pid-file, and wait for it to exit")
    p_stop.add_argument("pid_file")
    p_stop.add_argument("--timeout", type=float, default=10.0,
                         help="seconds to wait for the process to exit before reporting failure")
    p_stop.set_defaults(func=cmd_stop)

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
