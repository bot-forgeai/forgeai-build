"""Render an RSS 2.0 feed from a list of built pages."""
import datetime
from email.utils import format_datetime
from xml.sax.saxutils import escape


def _page_pubdate(page):
    """Parse a page's date field (YYYY-MM-DD) into RFC-822 for RSS, or None."""
    date_str = page.get("date")
    if not date_str:
        return None
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    return format_datetime(dt.replace(tzinfo=datetime.timezone.utc))


def render_rss(pages, site_title, base_url):
    """Build an RSS 2.0 XML string for pages, linking into base_url.

    base_url is the site's public root (e.g. "http://example.com"); each
    page's link is base_url + "/" + slug + ".html". Pages are emitted in
    the order given -- callers should pass them already sorted newest first.
    """
    root = base_url.rstrip("/")
    items = []
    for page in pages:
        link = f"{root}/{page['slug']}.html"
        title = escape(page.get("title", page["slug"]))
        item = [
            "<item>",
            f"<title>{title}</title>",
            f"<link>{escape(link)}</link>",
            f"<guid>{escape(link)}</guid>",
        ]
        pubdate = _page_pubdate(page)
        if pubdate:
            item.append(f"<pubDate>{pubdate}</pubDate>")
        item.append("</item>")
        items.append("\n".join(item))

    channel_title = escape(site_title)
    channel_link = escape(root)
    items_xml = "\n".join(items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "<channel>\n"
        f"<title>{channel_title}</title>\n"
        f"<link>{channel_link}</link>\n"
        f"{items_xml}\n"
        "</channel>\n"
        "</rss>\n"
    )
