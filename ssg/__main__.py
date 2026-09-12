"""Command-line interface for ssg: build and preview a static site."""
import argparse
import datetime
import functools
import http.server
import os
import re
import sys

from .build import build_site

DEFAULT_SITE_DIR = "site"


def _slugify(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


def cmd_build(args):
    site_dir = args.site
    content_dir = os.path.join(site_dir, "content")
    templates_dir = os.path.join(site_dir, "templates")
    static_dir = os.path.join(site_dir, "static")
    output_dir = args.output or os.path.join(site_dir, "_build")

    if not os.path.isdir(content_dir):
        print(f"error: no content directory at {content_dir}", file=sys.stderr)
        return 1

    pages = build_site(content_dir, templates_dir, output_dir, static_dir, args.title,
                        args.base_url)
    print(f"Built {len(pages)} page(s) into {output_dir}")
    if args.base_url:
        print(f"Wrote feed.xml (base URL: {args.base_url})")
    return 0


def cmd_new(args):
    site_dir = args.site
    posts_dir = os.path.join(site_dir, "content", "posts")
    os.makedirs(posts_dir, exist_ok=True)
    slug = _slugify(args.title)
    path = os.path.join(posts_dir, f"{slug}.md")
    if os.path.exists(path):
        print(f"error: {path} already exists", file=sys.stderr)
        return 1
    today = datetime.date.today().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"---\ntitle: {args.title}\ndate: {today}\n---\n\nWrite here.\n")
    print(f"Created {path}")
    return 0


def cmd_serve(args):
    site_dir = args.site
    output_dir = args.output or os.path.join(site_dir, "_build")
    content_dir = os.path.join(site_dir, "content")
    templates_dir = os.path.join(site_dir, "templates")
    static_dir = os.path.join(site_dir, "static")

    if not os.path.isdir(content_dir):
        print(f"error: no content directory at {content_dir}", file=sys.stderr)
        return 1

    build_site(content_dir, templates_dir, output_dir, static_dir, args.title, args.base_url)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=output_dir)
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {output_dir} on http://{args.host}:{server.server_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="ssg", description="A small static site generator")
    parser.add_argument("--site", default=DEFAULT_SITE_DIR, help="site directory (default: site)")
    parser.add_argument("--title", default="My Site", help="site title for the index page")
    parser.add_argument("--base-url", default=None,
                         help="public site root (e.g. https://example.com); "
                              "if given, also writes feed.xml")
    sub = parser.add_subparsers(dest="command", required=True)

    build_p = sub.add_parser("build", help="render content into static HTML")
    build_p.add_argument("--output", help="output directory (default: <site>/_build)")
    build_p.set_defaults(func=cmd_build)

    new_p = sub.add_parser("new", help="scaffold a new post")
    new_p.add_argument("title", help="post title")
    new_p.set_defaults(func=cmd_new)

    serve_p = sub.add_parser("serve", help="build and serve the site locally")
    serve_p.add_argument("--output", help="output directory (default: <site>/_build)")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8000)
    serve_p.set_defaults(func=cmd_serve)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
