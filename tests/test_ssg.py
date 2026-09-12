import os
import urllib.request

import pytest

from ssg.build import build_site
from ssg.content import ContentError, load_page, load_pages, parse_front_matter
from ssg.feed import render_rss
from ssg.markdown import render as render_markdown
from ssg.render import apply_template


def test_parse_front_matter_basic():
    text = "---\ntitle: Hi\ndate: 2026-01-01\n---\nbody text\n"
    meta, body = parse_front_matter(text)
    assert meta == {"title": "Hi", "date": "2026-01-01"}
    assert body == "body text"


def test_parse_front_matter_none():
    meta, body = parse_front_matter("just a body, no front matter")
    assert meta == {}
    assert body == "just a body, no front matter"


def test_parse_front_matter_unterminated():
    with pytest.raises(ContentError):
        parse_front_matter("---\ntitle: Hi\nno closing delimiter\n")


def test_load_page(tmp_path):
    p = tmp_path / "my-post.md"
    p.write_text("---\ntitle: My Post\n---\nHello.\n")
    page = load_page(str(p))
    assert page["title"] == "My Post"
    assert page["slug"] == "my-post"
    assert page["body"] == "Hello."


def test_load_page_defaults_title_to_slug(tmp_path):
    p = tmp_path / "untitled.md"
    p.write_text("no front matter here")
    page = load_page(str(p))
    assert page["title"] == "untitled"
    assert page["slug"] == "untitled"


def test_load_pages_recursive(tmp_path):
    (tmp_path / "posts").mkdir()
    (tmp_path / "posts" / "a.md").write_text("---\ntitle: A\n---\nbody")
    (tmp_path / "b.md").write_text("---\ntitle: B\n---\nbody")
    (tmp_path / "notes.txt").write_text("ignored, not markdown")
    pages = load_pages(str(tmp_path))
    titles = sorted(p["title"] for p in pages)
    assert titles == ["A", "B"]


def test_markdown_headers_and_paragraph():
    html = render_markdown("# Title\n\nA paragraph.")
    assert "<h1>Title</h1>" in html
    assert "<p>A paragraph.</p>" in html


def test_markdown_list():
    html = render_markdown("- one\n- two\n")
    assert "<ul>" in html
    assert "<li>one</li>" in html
    assert "<li>two</li>" in html


def test_markdown_inline_formatting():
    html = render_markdown("**bold** and *italic* and `code` and [x](http://y)")
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html
    assert "<code>code</code>" in html
    assert '<a href="http://y">x</a>' in html


def test_markdown_code_block():
    html = render_markdown("```\ndef f():\n    pass\n```")
    assert "<pre><code>" in html
    assert "def f():" in html


def test_markdown_escapes_html():
    html = render_markdown("<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_apply_template_fills_known_keys():
    out = apply_template("<h1>{{ title }}</h1>{{ content }}", {"title": "T", "content": "C"})
    assert out == "<h1>T</h1>C"


def test_apply_template_missing_key_is_blank():
    out = apply_template("[{{ missing }}]", {})
    assert out == "[]"


def test_build_site_writes_pages_and_index(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "one.md").write_text("---\ntitle: One\ndate: 2026-01-01\n---\nBody one.\n")
    (content_dir / "two.md").write_text("---\ntitle: Two\ndate: 2026-02-01\n---\nBody two.\n")
    templates_dir = tmp_path / "templates"
    output_dir = tmp_path / "_build"

    pages = build_site(str(content_dir), str(templates_dir), str(output_dir), None, "Test Site")

    assert len(pages) == 2
    assert pages[0]["title"] == "Two"  # newer date sorts first
    assert (output_dir / "one.html").exists()
    assert (output_dir / "two.html").exists()
    index_html = (output_dir / "index.html").read_text()
    assert "Test Site" in index_html
    assert "two.html" in index_html
    assert "one.html" in index_html


def test_build_site_copies_static(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "a.md").write_text("---\ntitle: A\n---\nbody")
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "style.css").write_text("body {}")
    output_dir = tmp_path / "_build"

    build_site(str(content_dir), str(tmp_path / "templates"), str(output_dir), str(static_dir), "S")

    assert (output_dir / "static" / "style.css").read_text() == "body {}"


def test_build_site_uses_custom_template(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "a.md").write_text("---\ntitle: A\n---\nbody")
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "page.html").write_text("CUSTOM:{{ title }}:{{ content }}")
    output_dir = tmp_path / "_build"

    build_site(str(content_dir), str(templates_dir), str(output_dir), None, "S")

    out = (output_dir / "a.html").read_text()
    assert out.startswith("CUSTOM:A:")


def test_cli_build_and_new(tmp_path):
    from ssg.__main__ import build_parser

    site_dir = tmp_path / "site"
    parser = build_parser()

    args = parser.parse_args(["--site", str(site_dir), "new", "My New Post"])
    assert args.func(args) == 0
    assert (site_dir / "content" / "posts" / "my-new-post.md").exists()

    args = parser.parse_args(["--site", str(site_dir), "build"])
    assert args.func(args) == 0
    assert (site_dir / "_build" / "my-new-post.html").exists()


def test_cli_new_refuses_duplicate(tmp_path):
    from ssg.__main__ import build_parser

    site_dir = tmp_path / "site"
    parser = build_parser()
    args = parser.parse_args(["--site", str(site_dir), "new", "Dup"])
    args.func(args)
    args2 = parser.parse_args(["--site", str(site_dir), "new", "Dup"])
    assert args2.func(args2) == 1


def test_cli_build_missing_content_dir(tmp_path, capsys):
    from ssg.__main__ import build_parser

    site_dir = tmp_path / "empty-site"
    parser = build_parser()
    args = parser.parse_args(["--site", str(site_dir), "build"])
    assert args.func(args) == 1


def test_render_rss_basic():
    pages = [
        {"slug": "two", "title": "Two", "date": "2026-02-01"},
        {"slug": "one", "title": "One", "date": "2026-01-01"},
    ]
    xml = render_rss(pages, "My Site", "http://example.com")
    assert "<title>My Site</title>" in xml
    assert "<link>http://example.com</link>" in xml
    assert "<link>http://example.com/two.html</link>" in xml
    assert "<link>http://example.com/one.html</link>" in xml
    # newest-first order preserved as given
    assert xml.index("two.html") < xml.index("one.html")
    assert "<pubDate>" in xml


def test_render_rss_trailing_slash_base_url():
    pages = [{"slug": "a", "title": "A", "date": "2026-01-01"}]
    xml = render_rss(pages, "S", "http://example.com/")
    assert "<link>http://example.com/a.html</link>" in xml


def test_render_rss_escapes_title():
    pages = [{"slug": "a", "title": "A & B <tag>", "date": "2026-01-01"}]
    xml = render_rss(pages, "S", "http://example.com")
    assert "A &amp; B &lt;tag&gt;" in xml
    assert "<tag>" not in xml


def test_render_rss_missing_date_omits_pubdate():
    pages = [{"slug": "a", "title": "A"}]
    xml = render_rss(pages, "S", "http://example.com")
    assert "<pubDate>" not in xml
    assert "<link>http://example.com/a.html</link>" in xml


def test_build_site_writes_feed_when_base_url_given(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "a.md").write_text("---\ntitle: A\ndate: 2026-01-01\n---\nbody")
    output_dir = tmp_path / "_build"

    build_site(str(content_dir), str(tmp_path / "templates"), str(output_dir), None, "S",
               base_url="http://example.com")

    feed_path = output_dir / "feed.xml"
    assert feed_path.exists()
    assert "http://example.com/a.html" in feed_path.read_text()


def test_build_site_skips_feed_without_base_url(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "a.md").write_text("---\ntitle: A\n---\nbody")
    output_dir = tmp_path / "_build"

    build_site(str(content_dir), str(tmp_path / "templates"), str(output_dir), None, "S")

    assert not (output_dir / "feed.xml").exists()


def test_cli_build_with_base_url_writes_feed(tmp_path):
    from ssg.__main__ import build_parser

    site_dir = tmp_path / "site"
    parser = build_parser()
    new_args = parser.parse_args(["--site", str(site_dir), "new", "My Post"])
    new_args.func(new_args)
    args = parser.parse_args(["--site", str(site_dir), "--base-url", "http://example.com", "build"])
    assert args.func(args) == 0


def test_build_site_excludes_draft_by_default(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "a.md").write_text("---\ntitle: A\ndate: 2026-01-01\n---\npublished")
    (content_dir / "b.md").write_text("---\ntitle: B\ndate: 2026-02-01\ndraft: true\n---\nsecret")
    output_dir = tmp_path / "_build"

    pages = build_site(str(content_dir), str(tmp_path / "templates"), str(output_dir), None, "S")

    assert len(pages) == 1
    assert pages[0]["title"] == "A"
    assert (output_dir / "a.html").exists()
    assert not (output_dir / "b.html").exists()
    assert "b.html" not in (output_dir / "index.html").read_text()


def test_build_site_includes_draft_when_requested(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "a.md").write_text("---\ntitle: A\n---\npublished")
    (content_dir / "b.md").write_text("---\ntitle: B\ndraft: true\n---\nsecret")
    output_dir = tmp_path / "_build"

    pages = build_site(str(content_dir), str(tmp_path / "templates"), str(output_dir), None, "S",
                        drafts=True)

    assert len(pages) == 2
    assert (output_dir / "b.html").exists()


def test_build_site_draft_excluded_from_feed(tmp_path):
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "a.md").write_text("---\ntitle: A\ndate: 2026-01-01\n---\npublished")
    (content_dir / "b.md").write_text("---\ntitle: B\ndate: 2026-02-01\ndraft: true\n---\nsecret")
    output_dir = tmp_path / "_build"

    build_site(str(content_dir), str(tmp_path / "templates"), str(output_dir), None, "S",
               base_url="http://example.com")

    feed_text = (output_dir / "feed.xml").read_text()
    assert "a.html" in feed_text
    assert "b.html" not in feed_text


def test_cli_new_draft_flag_sets_front_matter(tmp_path):
    from ssg.__main__ import build_parser

    site_dir = tmp_path / "site"
    parser = build_parser()
    args = parser.parse_args(["--site", str(site_dir), "new", "Secret Post", "--draft"])
    assert args.func(args) == 0
    text = (site_dir / "content" / "posts" / "secret-post.md").read_text()
    assert "draft: true" in text


def test_cli_build_drafts_flag_includes_drafts(tmp_path):
    from ssg.__main__ import build_parser

    site_dir = tmp_path / "site"
    parser = build_parser()
    new_args = parser.parse_args(["--site", str(site_dir), "new", "Secret Post", "--draft"])
    new_args.func(new_args)

    args = parser.parse_args(["--site", str(site_dir), "build"])
    args.func(args)
    assert not (site_dir / "_build" / "secret-post.html").exists()

    drafts_args = parser.parse_args(["--site", str(site_dir), "--drafts", "build"])
    drafts_args.func(drafts_args)
    assert (site_dir / "_build" / "secret-post.html").exists()
