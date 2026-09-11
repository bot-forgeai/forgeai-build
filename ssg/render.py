"""Apply a page's rendered HTML body to a simple {{ placeholder }} template."""
import re

_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def apply_template(template_text, context):
    """Replace {{ key }} placeholders with values from context.

    Missing keys render as an empty string rather than raising, since a
    template is often shared across pages with different optional fields
    (e.g. only posts have a date).
    """
    def replace(match):
        key = match.group(1)
        return str(context.get(key, ""))

    return _PLACEHOLDER.sub(replace, template_text)
