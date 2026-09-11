"""Parse content files: YAML-lite front matter plus a markdown body."""
import os

FRONT_MATTER_DELIM = "---"


class ContentError(Exception):
    pass


def parse_front_matter(text):
    """Split leading '---' delimited front matter from the body.

    Front matter is a restricted "key: value" format, one pair per line
    (no nested structures) -- enough for page metadata without pulling in
    a YAML dependency. Returns (metadata_dict, body_str).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONT_MATTER_DELIM:
        return {}, text

    meta = {}
    i = 1
    while i < len(lines) and lines[i].strip() != FRONT_MATTER_DELIM:
        line = lines[i]
        if line.strip() and ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
        i += 1

    if i >= len(lines):
        raise ContentError("unterminated front matter (missing closing '---')")

    body = "\n".join(lines[i + 1:]).lstrip("\n")
    return meta, body


def load_page(path):
    """Load a single content file into a dict: metadata + body + slug."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    meta, body = parse_front_matter(text)
    slug = os.path.splitext(os.path.basename(path))[0]
    page = dict(meta)
    page["body"] = body
    page.setdefault("slug", slug)
    page.setdefault("title", slug)
    return page


def load_pages(content_dir):
    """Load every .md file under content_dir (recursively) into a list of pages."""
    pages = []
    for root, _dirs, files in os.walk(content_dir):
        for name in sorted(files):
            if name.endswith(".md"):
                pages.append(load_page(os.path.join(root, name)))
    return pages
