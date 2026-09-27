import argparse
import os
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _get_version

from . import algorithms
from .model import Graph, GraphError
from .query import QueryError, execute, parse
from .storage import load, save


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def _parse_prop_value(raw):
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _parse_props(pairs):
    props = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(f"error: --prop must be key=value, got {pair!r}")
        key, _, raw_value = pair.partition("=")
        props[key] = _parse_prop_value(raw_value)
    return props


def _print_node(node_id, node):
    labels = ",".join(node["labels"]) or "-"
    props = " ".join(f"{k}={v!r}" for k, v in node["props"].items())
    print(f"{node_id}\t{labels}\t{props}")


def cmd_init(args):
    if os.path.exists(args.db):
        print(f"error: {args.db} already exists", file=sys.stderr)
        sys.exit(1)
    save(Graph(), args.db)
    print(f"initialized empty graph at {args.db}")


def cmd_add_node(args):
    graph = load(args.db)
    try:
        graph.add_node(args.id, labels=args.label, props=_parse_props(args.prop))
    except GraphError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    save(graph, args.db)
    print(f"added node {args.id!r}")


def cmd_remove_node(args):
    graph = load(args.db)
    try:
        graph.remove_node(args.id)
    except GraphError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    save(graph, args.db)
    print(f"removed node {args.id!r}")


def cmd_add_edge(args):
    graph = load(args.db)
    try:
        graph.add_edge(args.edge_id, args.from_id, args.to_id, args.type, props=_parse_props(args.prop))
    except GraphError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    save(graph, args.db)
    print(f"added edge {args.edge_id!r} ({args.from_id} -[{args.type}]-> {args.to_id})")


def cmd_remove_edge(args):
    graph = load(args.db)
    try:
        graph.remove_edge(args.edge_id)
    except GraphError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    save(graph, args.db)
    print(f"removed edge {args.edge_id!r}")


def cmd_query(args):
    graph = load(args.db)
    try:
        parsed = parse(args.query)
        rows = execute(graph, parsed)
    except (QueryError, GraphError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    if not rows:
        print("(0 rows)")
        return
    columns = list(rows[0].keys())
    print("\t".join(columns))
    for row in rows:
        print("\t".join(str(row[c]) for c in columns))
    print(f"({len(rows)} row(s))")


def cmd_shortest_path(args):
    graph = load(args.db)
    try:
        path = algorithms.shortest_path(graph, args.start, args.end, edge_type=args.type)
    except GraphError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    if path is None:
        print(f"no path from {args.start!r} to {args.end!r}")
        sys.exit(1)
    print(" -> ".join(path))


def cmd_components(args):
    graph = load(args.db)
    components = algorithms.connected_components(graph)
    for i, component in enumerate(components):
        print(f"component {i}: {', '.join(component)}")
    print(f"({len(components)} component(s))")


def cmd_stats(args):
    graph = load(args.db)
    print(f"nodes: {len(graph.nodes)}")
    print(f"edges: {len(graph.edges)}")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="graphlite", description="a tiny property graph store with a MATCH query language"
    )
    parser.add_argument("--version", action="version", version=_get_package_version())
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create a new empty graph database file")
    p_init.add_argument("db")
    p_init.set_defaults(func=cmd_init)

    p_add_node = sub.add_parser("add-node", help="add a node")
    p_add_node.add_argument("db")
    p_add_node.add_argument("id")
    p_add_node.add_argument("--label", action="append", help="repeatable")
    p_add_node.add_argument("--prop", action="append", help="key=value, repeatable")
    p_add_node.set_defaults(func=cmd_add_node)

    p_remove_node = sub.add_parser("remove-node", help="remove a node and its incident edges")
    p_remove_node.add_argument("db")
    p_remove_node.add_argument("id")
    p_remove_node.set_defaults(func=cmd_remove_node)

    p_add_edge = sub.add_parser("add-edge", help="add a directed, typed edge between two nodes")
    p_add_edge.add_argument("db")
    p_add_edge.add_argument("edge_id")
    p_add_edge.add_argument("from_id")
    p_add_edge.add_argument("to_id")
    p_add_edge.add_argument("type")
    p_add_edge.add_argument("--prop", action="append", help="key=value, repeatable")
    p_add_edge.set_defaults(func=cmd_add_edge)

    p_remove_edge = sub.add_parser("remove-edge", help="remove an edge")
    p_remove_edge.add_argument("db")
    p_remove_edge.add_argument("edge_id")
    p_remove_edge.set_defaults(func=cmd_remove_edge)

    p_query = sub.add_parser("query", help="run a MATCH/WHERE/RETURN query")
    p_query.add_argument("db")
    p_query.add_argument("query")
    p_query.set_defaults(func=cmd_query)

    p_sp = sub.add_parser("shortest-path", help="BFS shortest path between two nodes")
    p_sp.add_argument("db")
    p_sp.add_argument("start")
    p_sp.add_argument("end")
    p_sp.add_argument("--type", help="restrict traversal to this edge type")
    p_sp.set_defaults(func=cmd_shortest_path)

    p_components = sub.add_parser("components", help="list weakly-connected components")
    p_components.add_argument("db")
    p_components.set_defaults(func=cmd_components)

    p_stats = sub.add_parser("stats", help="print node/edge counts")
    p_stats.add_argument("db")
    p_stats.set_defaults(func=cmd_stats)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
