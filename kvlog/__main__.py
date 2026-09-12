import argparse
import json
import sys

from .store import KVStore


def cmd_put(args):
    with KVStore(args.db) as store:
        store.put(args.key, args.value)
    print(f"put {args.key!r}")


def cmd_get(args):
    with KVStore(args.db) as store:
        if args.key not in store:
            print(f"error: no such key {args.key!r}", file=sys.stderr)
            sys.exit(1)
        print(store.get(args.key))


def cmd_delete(args):
    with KVStore(args.db) as store:
        if not store.delete(args.key):
            print(f"error: no such key {args.key!r}", file=sys.stderr)
            sys.exit(1)
    print(f"deleted {args.key!r}")


def cmd_keys(args):
    with KVStore(args.db) as store:
        for key in store.keys():
            print(key)


def cmd_dump(args):
    with KVStore(args.db) as store:
        for key, value in store.items():
            print(f"{key}\t{json.dumps(value)}")


def cmd_compact(args):
    with KVStore(args.db) as store:
        before = _log_size(args.db)
        store.compact()
        after = _log_size(args.db)
    print(f"compacted: {before} -> {after} bytes, {len(store)} keys")


def _log_size(path):
    import os

    return os.path.getsize(path) if os.path.exists(path) else 0


def build_parser():
    parser = argparse.ArgumentParser(prog="kvlog", description="append-only log-structured key-value store")
    parser.add_argument("--db", default="kvlog.db", help="path to the log file (default: kvlog.db)")
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

    p_compact = sub.add_parser("compact", help="rewrite the log, dropping stale history")
    p_compact.set_defaults(func=cmd_compact)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
