import argparse
import sys
import time

from raftlite import __doc__ as _unused  # noqa: F401
from raftlite.server import RaftServer
from raftlite.transport import client_request

VERSION = "0.1.0"


def parse_peers(peers_arg):
    """'1=host:port,2=host:port' -> {1: (host, port), 2: (host, port)}"""
    result = {}
    if not peers_arg:
        return result
    for item in peers_arg.split(","):
        id_part, addr_part = item.split("=")
        host, port = addr_part.rsplit(":", 1)
        result[int(id_part)] = (host, int(port))
    return result


def cmd_node(args):
    peers = parse_peers(args.peers)
    server = RaftServer(args.id, (args.host, args.port), peers)
    server.start()
    print(f"raftlite node {args.id} listening on {args.host}:{args.port}, peers={peers}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("shutting down")
        server.stop()


def _address(addr_str):
    host, port = addr_str.rsplit(":", 1)
    return (host, int(port))


def cmd_put(args):
    response = client_request(_address(args.address), {"type": "PUT", "key": args.key, "value": args.value})
    if response["status"] == "NOT_LEADER":
        print(f"error: not the leader (leader_id={response.get('leader_id')})", file=sys.stderr)
        sys.exit(1)
    if response["status"] != "OK":
        print(f"error: {response}", file=sys.stderr)
        sys.exit(1)
    print(f"OK (index {response['index']})")


def cmd_get(args):
    response = client_request(_address(args.address), {"type": "GET", "key": args.key})
    if response.get("found"):
        print(response["value"])
    else:
        print("(not found)")
        sys.exit(1)


def cmd_delete(args):
    response = client_request(_address(args.address), {"type": "DELETE", "key": args.key})
    if response["status"] == "NOT_LEADER":
        print(f"error: not the leader (leader_id={response.get('leader_id')})", file=sys.stderr)
        sys.exit(1)
    if response["status"] != "OK":
        print(f"error: {response}", file=sys.stderr)
        sys.exit(1)
    print(f"OK (index {response['index']})")


def cmd_status(args):
    response = client_request(_address(args.address), {"type": "STATUS"})
    print(f"role={response['role']} term={response['term']} leader_id={response['leader_id']} "
          f"commit_index={response['commit_index']} last_applied={response['last_applied']}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="raftlite", description="A small Raft consensus KV store.")
    parser.add_argument("--version", action="version", version=f"raftlite {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_node = sub.add_parser("node", help="run a raftlite cluster node")
    p_node.add_argument("--id", type=int, required=True)
    p_node.add_argument("--host", default="127.0.0.1")
    p_node.add_argument("--port", type=int, required=True)
    p_node.add_argument("--peers", default="", help="comma-separated id=host:port list of other nodes")
    p_node.set_defaults(func=cmd_node)

    p_put = sub.add_parser("put", help="write a key/value pair via a running node")
    p_put.add_argument("address", help="host:port of any node to contact")
    p_put.add_argument("key")
    p_put.add_argument("value")
    p_put.set_defaults(func=cmd_put)

    p_get = sub.add_parser("get", help="read a key via a running node")
    p_get.add_argument("address")
    p_get.add_argument("key")
    p_get.set_defaults(func=cmd_get)

    p_delete = sub.add_parser("delete", help="delete a key via a running node")
    p_delete.add_argument("address")
    p_delete.add_argument("key")
    p_delete.set_defaults(func=cmd_delete)

    p_status = sub.add_parser("status", help="show a node's role/term/commit state")
    p_status.add_argument("address")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
