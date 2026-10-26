import argparse
import json
import os
import sys
import time
from importlib.metadata import version as _get_version, PackageNotFoundError

from searchlite.tokenize import tokenize
from searchlite.storage import IndexCorruptError, load_or_new_index, save_index


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def cmd_add(args):
    index = load_or_new_index(args.index)
    for path in args.paths:
        if not os.path.isfile(path):
            print(f"error: no such file {path!r}", file=sys.stderr)
            sys.exit(1)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        doc_id = os.path.relpath(path, args.base)
        if args.lines:
            n = 0
            for lineno, line in enumerate(text.splitlines(), 1):
                if line.strip():
                    index.add_document(f"{doc_id}:{lineno}", line)
                    n += 1
            print(f"indexed {n} lines of {doc_id!r}")
            continue
        index.add_document(doc_id, text)
        print(f"indexed {doc_id!r}")
    save_index(index, args.index)


def _sync_dir(index, directory, base, extensions, prune, stat_cache=None):
    """Bring the index in line with directory; returns (indexed, unchanged, pruned)."""
    count = unchanged = pruned = 0
    seen = set()
    for root, _dirs, files in os.walk(directory):
        for name in sorted(files):
            if not name.endswith(extensions):
                continue
            path = os.path.join(root, name)
            doc_id = os.path.relpath(path, base)
            seen.add(doc_id)
            if stat_cache is not None:
                st = os.stat(path)
                sig = (st.st_mtime_ns, st.st_size)
                if stat_cache.get(doc_id) == sig and doc_id in index.doc_texts:
                    unchanged += 1
                    continue
                stat_cache[doc_id] = sig
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            if index.doc_texts.get(doc_id) == text:
                unchanged += 1
                continue
            index.add_document(doc_id, text)
            count += 1
    if prune:
        prefix = os.path.relpath(directory, base).rstrip(os.sep) + os.sep
        for doc_id in [d for d in index.doc_lengths if d.startswith(prefix) and d not in seen]:
            index.remove_document(doc_id)
            pruned += 1
    return count, unchanged, pruned


def _parse_exts(ext):
    return tuple(e if e.startswith(".") else f".{e}" for e in ext.split(","))


def cmd_add_dir(args):
    index = load_or_new_index(args.index, rebuild=args.rebuild)
    count, unchanged, pruned = _sync_dir(index, args.directory, args.base, _parse_exts(args.ext), args.prune)
    save_index(index, args.index)
    msg = f"indexed {count} file(s)"
    if unchanged:
        msg += f", {unchanged} unchanged"
    if args.prune:
        msg += f", {pruned} pruned"
    print(msg)


def _file_sig(path):
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    return (st.st_mtime_ns, st.st_size)


def cmd_watch(args):
    extensions = _parse_exts(args.ext)
    runs = 0
    index = load_or_new_index(args.index, rebuild=args.rebuild)
    index_sig = _file_sig(args.index)
    stat_cache = {}  # doc_id -> (mtime_ns, size): unchanged files aren't re-read on later scans
    while True:
        if _file_sig(args.index) != index_sig:  # someone else (add, remove) rewrote the index
            index = load_or_new_index(args.index)
        count, _unchanged, pruned = _sync_dir(index, args.directory, args.base, extensions, not args.no_prune, stat_cache)
        if count or pruned:
            save_index(index, args.index)
            index_sig = _file_sig(args.index)
            print(f"synced: {count} indexed, {pruned} pruned", flush=True)
        runs += 1
        if args.max_runs and runs >= args.max_runs:
            return
        time.sleep(args.interval)


def cmd_remove(args):
    index = load_or_new_index(args.index)
    if not index.remove_document(args.doc_id):
        print(f"error: no such document {args.doc_id!r}", file=sys.stderr)
        sys.exit(1)
    save_index(index, args.index)
    print(f"removed {args.doc_id!r}")


def cmd_search(args):
    if args.top < 1:
        print(f"error: --top must be a positive number, got {args.top}", file=sys.stderr)
        sys.exit(2)
    if not tokenize(args.query):
        print(f"error: query {args.query!r} has no searchable terms (blank or only stopwords)", file=sys.stderr)
        sys.exit(2)
    index = load_or_new_index(args.index)
    if args.phrase:
        results = index.search_phrase(args.query, top_k=args.top)
    else:
        results = index.search(args.query, top_k=args.top, rank=args.rank)
    if not results and not args.json:
        print("no results")
        return
    rows = []
    for doc_id, score in results:
        if args.snippet:
            preview = index.snippet(doc_id, args.query)
        else:
            preview = index.doc_titles.get(doc_id, "")
        rows.append((doc_id, score, preview))
    if args.json:
        print(json.dumps([{"doc_id": d, "score": round(s, 4), "preview": p} for d, s, p in rows]))
        return
    for doc_id, score, preview in rows:
        print(f"{score:.4f}\t{doc_id}\t{preview}")


def cmd_stats(args):
    index = load_or_new_index(args.index)
    print(f"documents: {index.doc_count}")
    print(f"terms: {len(index.postings)}")


def build_parser():
    parser = argparse.ArgumentParser(prog="searchlite", description="tiny full-text search engine (inverted index + TF-IDF)")
    parser.add_argument("--version", action="version", version=_get_package_version())
    parser.add_argument("--index", default=os.environ.get("SEARCHLITE_INDEX", "searchlite.json"), help="path to the index file (default: $SEARCHLITE_INDEX, else searchlite.json)")
    parser.add_argument("--base", default=None, help="directory doc ids are made relative to (default: current directory), so ids don't depend on where you run from")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="index one or more text files")
    p_add.add_argument("paths", nargs="+")
    p_add.add_argument("--lines", action="store_true", help="index each non-blank line as its own document (id path:LINE), e.g. one recall card per line")
    p_add.set_defaults(func=cmd_add)

    p_add_dir = sub.add_parser("add-dir", help="index every matching file under a directory")
    p_add_dir.add_argument("directory")
    p_add_dir.add_argument("--ext", default=".txt,.md", help="comma-separated extensions to index (default: .txt,.md)")
    p_add_dir.add_argument("--prune", action="store_true", help="remove indexed docs under the directory whose files no longer exist")
    p_add_dir.add_argument("--rebuild", action="store_true", help="if the index file is corrupt, move it to INDEX.corrupt and rebuild from the directory")
    p_add_dir.set_defaults(func=cmd_add_dir)

    p_watch = sub.add_parser("watch", help="poll a directory and reindex whenever files change, are added or deleted")
    p_watch.add_argument("directory")
    p_watch.add_argument("--ext", default=".txt,.md", help="comma-separated extensions to index (default: .txt,.md)")
    p_watch.add_argument("--interval", type=float, default=5.0, help="seconds between scans (default: 5)")
    p_watch.add_argument("--max-runs", type=int, default=0, help="stop after this many scans (default: 0 = run until interrupted)")
    p_watch.add_argument("--no-prune", action="store_true", help="keep docs whose files were deleted")
    p_watch.add_argument("--rebuild", action="store_true", help="if the index file is corrupt, move it to INDEX.corrupt and rebuild from the directory")
    p_watch.set_defaults(func=cmd_watch)

    p_remove = sub.add_parser("remove", help="remove a document from the index by its doc id (path)")
    p_remove.add_argument("doc_id")
    p_remove.set_defaults(func=cmd_remove)

    p_search = sub.add_parser("search", help="search the index and print ranked results")
    p_search.add_argument("query")
    p_search.add_argument("--top", type=int, default=10, help="max number of results (default: 10)")
    p_search.add_argument("--snippet", action="store_true", help="show a query-term-highlighted excerpt instead of the leading preview")
    p_search.add_argument("--rank", choices=["tfidf", "bm25"], default="tfidf", help="ranking method (default: tfidf)")
    p_search.add_argument("--phrase", action="store_true", help="require query terms to appear as an exact consecutive phrase, ranked by occurrence count instead of tfidf/bm25")
    p_search.add_argument("--json", action="store_true", help="print results as a JSON array of {doc_id, score, preview} ('[]' when nothing matches)")
    p_search.set_defaults(func=cmd_search)

    p_stats = sub.add_parser("stats", help="print index size stats")
    p_stats.set_defaults(func=cmd_stats)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except IndexCorruptError as e:
        print(f"error: index is corrupt: {e}", file=sys.stderr)
        print("hint: restore a copy, or run 'add-dir DIR --rebuild' to set it aside as .corrupt and reindex", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
