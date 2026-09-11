"""A small markdown-subset -> HTML renderer (headers, lists, code, emphasis,
links, paragraphs). Not CommonMark-complete, but enough for real prose."""
import html
import re

_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"\*([^*]+)\*")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _render_inline(text):
    text = html.escape(text, quote=False)
    text = _INLINE_CODE.sub(lambda m: f"<code>{m.group(1)}</code>", text)
    text = _BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", text)
    text = _ITALIC.sub(lambda m: f"<em>{m.group(1)}</em>", text)
    text = _LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    return text


def render(source):
    """Render a markdown-subset document to an HTML fragment."""
    lines = source.splitlines()
    out = []
    i = 0
    paragraph = []
    list_items = None

    def flush_paragraph():
        if paragraph:
            out.append("<p>" + _render_inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def flush_list():
        nonlocal list_items
        if list_items is not None:
            out.append("<ul>")
            for item in list_items:
                out.append(f"<li>{_render_inline(item)}</li>")
            out.append("</ul>")
            list_items = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code = html.escape("\n".join(code_lines))
            out.append(f"<pre><code>{code}</code></pre>")
            i += 1
            continue

        header_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if header_match:
            flush_paragraph()
            flush_list()
            level = len(header_match.group(1))
            out.append(f"<h{level}>{_render_inline(header_match.group(2))}</h{level}>")
            i += 1
            continue

        list_match = re.match(r"^[-*]\s+(.*)$", stripped)
        if list_match:
            flush_paragraph()
            if list_items is None:
                list_items = []
            list_items.append(list_match.group(1))
            i += 1
            continue

        if not stripped:
            flush_paragraph()
            flush_list()
            i += 1
            continue

        flush_list()
        paragraph.append(stripped)
        i += 1

    flush_paragraph()
    flush_list()
    return "\n".join(out)
