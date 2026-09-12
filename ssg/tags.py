"""Group pages by tag and render tag index/listing pages.

Front matter has no list syntax (see content.py's restricted key: value
format), so a page's tags are a single comma-separated string, e.g.
`tags: python, tutorial`.
"""
import re


def parse_tags(page):
    """Return a page's tags as a list of stripped, non-empty strings."""
    raw = page.get("tags", "")
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def slugify_tag(tag):
    slug = re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")
    return slug or "tag"


def group_by_tag(pages):
    """Return {tag: [pages]} in first-seen tag order, pages in input order."""
    groups = {}
    for page in pages:
        for tag in parse_tags(page):
            groups.setdefault(tag, []).append(page)
    return groups
