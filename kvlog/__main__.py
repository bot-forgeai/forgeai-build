import argparse
import json
import os
import sys

from .client import RemoteError, call
from .server import serve
from .store import KVStore


def _parse_remote(remote):
    host, _, port = remote.partition(":")
    if not port:
        raise ValueError(f"--remote must be HOST:PORT, got {remote!r}")
    return host, int(port)


def cmd_put(args):
    if args.remote:
        host, port = _parse_remote(args.remote)
        call(host, port, "put", key=args.key, value=args.value)
    else:
        with KVStore(args.db, fsync=args.fsync) as store:
            store.put(args.key, args.value)
    print(f"put {args.key!r}")


def cmd_get(args):
    if args.remote:
        host, port = _parse_remote(args.remote)
        response = call(host, port, "get", key=args.key)
        print(response["value"])
    else:
        with KVStore(args.db, fsync=args.fsync) as store:
            if args.key not in store:
                print(f"error: no such key {args.key!r}", file=sys.stderr)
                sys.exit(1)
            print(store.get(args.key))


def cmd_delete(args):
    if args.remote:
        host, port = _parse_remote(args.remote)
        call(host, port, "delete", key=args.key)
    else:
        with KVStore(args.db, fsync=args.fsync) as store:
            if not store.delete(args.key):
                print(f"error: no such key {args.key!r}", file=sys.stderr)
                sys.exit(1)
    print(f"deleted {args.key!r}")


def cmd_keys(args):
    if args.remote:
        host, port = _parse_remote(args.remote)
        response = call(host, port, "keys")
        for key in response["keys"]:
            print(key)
    else:
        with KVStore(args.db, fsync=args.fsync) as store:
            for key in store.keys():
                print(key)


def cmd_dump(args):
    if args.remote:
        host, port = _parse_remote(args.remote)
        response = call(host, port, "dump")
        for key, value in response["items"]:
            print(f"{key}\t{json.dumps(value)}")
    else:
        with KVStore(args.db, fsync=args.fsync) as store:
            for key, value in store.items():
                print(f"{key}\t{json.dumps(value)}")


def cmd_prefix(args):
    if args.remote:
        host, port = _parse_remote(args.remote)
        response = call(host, port, "prefix", prefix=args.prefix)
        for key, value in response["items"]:
            print(f"{key}\t{json.dumps(value)}")
    else:
        with KVStore(args.db, fsync=args.fsync) as store:
            for key, value in store.prefix(args.prefix):
                print(f"{key}\t{json.dumps(value)}")


def cmd_range(args):
    if args.remote:
        host, port = _parse_remote(args.remote)
        response = call(host, port, "range", start=args.start, end=args.end)
        for key, value in response["items"]:
            print(f"{key}\t{json.dumps(value)}")
    else:
        with KVStore(args.db, fsync=args.fsync) as store:
            for key, value in store.range(args.start, args.end):
                print(f"{key}\t{json.dumps(value)}")


def cmd_compact(args):
    if args.remote:
        host, port = _parse_remote(args.remote)
        response = call(host, port, "compact")
        print(f"compacted: {response['before']} -> {response['after']} bytes, {response['count']} keys")
    else:
        with KVStore(args.db, fsync=args.fsync) as store:
            before = _log_size(args.db)
            store.compact()
            after = _log_size(args.db)
        print(f"compacted: {before} -> {after} bytes, {len(store)} keys")


def cmd_serve(args):
    print(f"kvlog serving {args.db} on {args.host}:{args.port} (fsync={args.fsync})")
    serve(args.host, args.port, args.db, fsync=args.fsync)


def _log_size(path):
    return os.path.getsize(path) if os.path.exists(path) else 0


def build_parser():
    parser = argparse.ArgumentParser(prog="kvlog", description="append-only log-structured key-value store")
    parser.add_argument("--db", default="kvlog.db", help="path to the log file (default: kvlog.db)")
    parser.add_argument(
        "--remote",
        default=None,
        help="HOST:PORT of a running 'kvlog serve' to talk to instead of opening --db locally",
    )
    parser.add_argument(
        "--fsync",
        choices=["always", "never"],
        default="always",
        help="fsync every write to disk before returning ('always', the safe default) or "
        "just flush to the OS page cache ('never', faster but a power loss can lose the "
        "last few writes even though the process itself would have recovered them)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_put = sub.add_parser("put", help="set a key's value")
    p_put.add_argument("key")
    p_put.add_argument("value")
    p_put.set_defaults(func=cmd_put)

    p_get = sub.add_parser("get", help="read a key's value")
    p_get.add_argument("key")
    p_get.set_defaults(func=cmd_get)

    p_delete = sub.add_parser("delete", help="delete a key")
    p_delete.add_argument("key")
    p_delete.set_defaults(func=cmd_delete)

    p_keys = sub.add_parser("keys", help="list all keys")
    p_keys.set_defaults(func=cmd_keys)

    p_dump = sub.add_parser("dump", help="print every key/value pair")
    p_dump.set_defaults(func=cmd_dump)

    p_prefix = sub.add_parser("prefix", help="list all key/value pairs whose key starts with a prefix")
    p_prefix.add_argument("prefix")
    p_prefix.set_defaults(func=cmd_prefix)

    p_range = sub.add_parser("range", help="list all key/value pairs with start <= key <= end")
    p_range.add_argument("--start", default=None, help="inclusive lower bound (omit for unbounded)")
    p_range.add_argument("--end", default=None, help="inclusive upper bound (omit for unbounded)")
    p_range.set_defaults(func=cmd_range)

    p_compact = sub.add_parser("compact", help="rewrite the log, dropping stale history")
    p_compact.set_defaults(func=cmd_compact)

    p_serve = sub.add_parser("serve", help="serve --db over TCP for remote --remote clients")
    p_serve.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1; use 0.0.0.0 for LAN)")
    p_serve.add_argument("--port", type=int, default=9999, help="bind port (default: 9999)")
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except RemoteError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
