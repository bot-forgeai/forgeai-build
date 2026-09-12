"""Build a static site: content/*.md -> output/*.html, plus an index page."""
import os
import shutil

from .content import load_pages
from .feed import render_rss
from .markdown import render as render_markdown
from .render import apply_template
from .tags import group_by_tag, parse_tags, slugify_tag

DEFAULT_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{{ title }}</title></head>
<body>
<h1>{{ title }}</h1>
<div class="meta">{{ date }} {{ tags }}</div>
{{ content }}
</body>
</html>
"""

DEFAULT_INDEX_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{{ title }}</title></head>
<body>
<h1>{{ title }}</h1>
{{ content }}
</body>
</html>
"""

DEFAULT_TAG_TEMPLATE = DEFAULT_INDEX_TEMPLATE
DEFAULT_TAG_INDEX_TEMPLATE = DEFAULT_INDEX_TEMPLATE


def _read_template(templates_dir, name, fallback):
    path = os.path.join(templates_dir, name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return fallback


def _is_draft(page):
    return str(page.get("draft", "")).strip().lower() in ("true", "yes", "1")


def _tag_links(tags, prefix):
    if not tags:
        return ""
    return " ".join(f'<a href="{prefix}{slugify_tag(t)}.html">{t}</a>' for t in tags)


def _write_tag_pages(pages, templates_dir, output_dir, site_title):
    """Write one listing page per tag, plus a tags/index.html of all tags."""
    groups = group_by_tag(pages)
    if not groups:
        return

    tags_dir = os.path.join(output_dir, "tags")
    os.makedirs(tags_dir, exist_ok=True)
    tag_template = _read_template(templates_dir, "tag.html", DEFAULT_TAG_TEMPLATE)
    tag_index_template = _read_template(templates_dir, "tags_index.html", DEFAULT_TAG_INDEX_TEMPLATE)

    for tag, tag_pages in groups.items():
        links = "<ul>\n" + "\n".join(
            f'<li><a href="../{p["slug"]}.html">{p["title"]}</a> {p.get("date", "")}</li>'
            for p in tag_pages
        ) + "\n</ul>"
        context = {"title": f"Tag: {tag}", "content": links}
        html = apply_template(tag_template, context)
        with open(os.path.join(tags_dir, f"{slugify_tag(tag)}.html"), "w", encoding="utf-8") as f:
            f.write(html)

    index_links = "<ul>\n" + "\n".join(
        f'<li><a href="{slugify_tag(tag)}.html">{tag}</a> ({len(tag_pages)})'
        for tag, tag_pages in groups.items()
    ) + "\n</ul>"
    index_context = {"title": f"Tags — {site_title}", "content": index_links}
    index_html = apply_template(tag_index_template, index_context)
    with open(os.path.join(tags_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)


def build_site(content_dir, templates_dir, output_dir, static_dir=None, site_title="My Site",
                base_url=None, drafts=False):
    """Render every content page plus an index, writing HTML into output_dir.

    If base_url is given, also writes an RSS feed to feed.xml -- feed
    links need an absolute URL, so the feed is skipped without one.

    A page with a front-matter `draft: true` field is excluded from the
    build (and the feed) unless drafts=True is passed.

    Returns the list of page dicts that were built (useful for tests).
    """
    pages = load_pages(content_dir)
    if not drafts:
        pages = [p for p in pages if not _is_draft(p)]
    pages.sort(key=lambda p: p.get("date", ""), reverse=True)

    os.makedirs(output_dir, exist_ok=True)
    page_template = _read_template(templates_dir, "page.html", DEFAULT_TEMPLATE)
    index_template = _read_template(templates_dir, "index.html", DEFAULT_INDEX_TEMPLATE)

    for page in pages:
        html_body = render_markdown(page["body"])
        context = dict(page)
        context["content"] = html_body
        context["tags"] = _tag_links(parse_tags(page), "tags/")
        out_html = apply_template(page_template, context)
        out_path = os.path.join(output_dir, f"{page['slug']}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out_html)

    links = "<ul>\n" + "\n".join(
        f'<li><a href="{p["slug"]}.html">{p["title"]}</a> {p.get("date", "")}</li>'
        for p in pages
    ) + "\n</ul>"
    index_context = {"title": site_title, "content": links}
    index_html = apply_template(index_template, index_context)
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    _write_tag_pages(pages, templates_dir, output_dir, site_title)

    if static_dir and os.path.isdir(static_dir):
        dest = os.path.join(output_dir, "static")
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(static_dir, dest)

    if base_url:
        rss = render_rss(pages, site_title, base_url)
        with open(os.path.join(output_dir, "feed.xml"), "w", encoding="utf-8") as f:
            f.write(rss)

    return pages
