import argparse
import os
import sys

from searchlite.storage import load_or_new_index, save_index


def cmd_add(args):
    index = load_or_new_index(args.index)
    for path in args.paths:
        if not os.path.isfile(path):
            print(f"error: no such file {path!r}", file=sys.stderr)
            sys.exit(1)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        doc_id = os.path.relpath(path)
        index.add_document(doc_id, text)
        print(f"indexed {doc_id!r}")
    save_index(index, args.index)


def cmd_add_dir(args):
    index = load_or_new_index(args.index)
    extensions = tuple(e if e.startswith(".") else f".{e}" for e in args.ext.split(","))
    count = 0
    for root, _dirs, files in os.walk(args.directory):
        for name in sorted(files):
            if not name.endswith(extensions):
                continue
            path = os.path.join(root, name)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            doc_id = os.path.relpath(path)
            index.add_document(doc_id, text)
            count += 1
    save_index(index, args.index)
    print(f"indexed {count} file(s)")


def cmd_remove(args):
    index = load_or_new_index(args.index)
    if not index.remove_document(args.doc_id):
        print(f"error: no such document {args.doc_id!r}", file=sys.stderr)
        sys.exit(1)
    save_index(index, args.index)
    print(f"removed {args.doc_id!r}")


def cmd_search(args):
    index = load_or_new_index(args.index)
    results = index.search(args.query, top_k=args.top)
    if not results:
        print("no results")
        return
    for doc_id, score in results:
        preview = index.doc_titles.get(doc_id, "")
        print(f"{score:.4f}\t{doc_id}\t{preview}")


def cmd_stats(args):
    index = load_or_new_index(args.index)
    print(f"documents: {index.doc_count}")
    print(f"terms: {len(index.postings)}")


def build_parser():
    parser = argparse.ArgumentParser(prog="searchlite", description="tiny full-text search engine (inverted index + TF-IDF)")
    parser.add_argument("--index", default="searchlite.json", help="path to the index file (default: searchlite.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="index one or more text files")
    p_add.add_argument("paths", nargs="+")
    p_add.set_defaults(func=cmd_add)

    p_add_dir = sub.add_parser("add-dir", help="index every matching file under a directory")
    p_add_dir.add_argument("directory")
    p_add_dir.add_argument("--ext", default=".txt,.md", help="comma-separated extensions to index (default: .txt,.md)")
    p_add_dir.set_defaults(func=cmd_add_dir)

    p_remove = sub.add_parser("remove", help="remove a document from the index by its doc id (path)")
    p_remove.add_argument("doc_id")
    p_remove.set_defaults(func=cmd_remove)

    p_search = sub.add_parser("search", help="search the index and print ranked results")
    p_search.add_argument("query")
    p_search.add_argument("--top", type=int, default=10, help="max number of results (default: 10)")
    p_search.set_defaults(func=cmd_search)

    p_stats = sub.add_parser("stats", help="print index size stats")
    p_stats.set_defaults(func=cmd_stats)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
