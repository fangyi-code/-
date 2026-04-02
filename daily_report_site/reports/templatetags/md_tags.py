import bleach
import markdown as md_lib
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = list(
    set(bleach.sanitizer.ALLOWED_TAGS)
    | {
        "p",
        "pre",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "hr",
    }
)
ALLOWED_ATTRS = dict(bleach.sanitizer.ALLOWED_ATTRIBUTES)
ALLOWED_ATTRS["a"] = ["href", "title", "rel"]
ALLOWED_ATTRS["th"] = ["colspan", "rowspan"]
ALLOWED_ATTRS["td"] = ["colspan", "rowspan"]


@register.filter(name="render_md")
def render_md(text: str) -> str:
    if not text:
        return ""
    raw = md_lib.markdown(
        text,
        extensions=["extra", "nl2br"],
        output_format="html",
    )
    clean = bleach.clean(raw, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
    return mark_safe(clean)
