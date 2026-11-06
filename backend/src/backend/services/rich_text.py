"""Post text as the editor writes it: HTML kept to a short list of tags, and its plain-text form."""

import html
import re

import nh3

TAGS = {"p", "br", "h2", "h3", "strong", "em", "s", "a", "ul", "ol", "li", "blockquote", "img"}
ATTRIBUTES = {"a": {"href"}, "img": {"src", "alt"}}
UPLOADED = re.compile(r"^/api/files/[0-9a-f-]{36}/(\?w=\d{1,5})?$")
SITE_PATH = re.compile(r"^/(?![/\\])")
UNSAFE = re.compile(r"[\s\\\x00-\x1f\x7f]")
BLOCK_END = re.compile(r"</(p|h2|h3|li|blockquote)>|<br\s*/?>", re.IGNORECASE)
SPACES = re.compile(r"[ \t]+")
TRAILING_EMPTY = re.compile(r"(<p>(\s|<br>)*</p>)+$")


def _attribute(tag: str, name: str, value: str) -> str | None:
    """Links go to https, mailto or this site; images come from https or this site's uploads."""
    if tag == "a" and name == "href":
        ok = value.startswith(("https://", "mailto:")) or SITE_PATH.match(value)
        return value if ok and not UNSAFE.search(value) else None
    if tag == "img" and name == "src":
        return value if value.startswith("https://") or UPLOADED.match(value) else None
    return value


def clean(value: str) -> str:
    """The HTML with every other tag, attribute and script removed; empty when nothing is left."""
    out = nh3.clean(
        value,
        tags=TAGS,
        attributes=ATTRIBUTES,
        attribute_filter=_attribute,
        url_schemes={"https", "mailto"},
        link_rel="noopener noreferrer",
    ).strip()
    out = TRAILING_EMPTY.sub("", out)
    return out if text(out) or "<img" in out else ""


def text(value: str) -> str:
    """The words of the HTML, one block per line."""
    marked = BLOCK_END.sub("\n", value)
    plain = html.unescape(nh3.clean(marked, tags=set()))
    lines = (SPACES.sub(" ", line).strip() for line in plain.split("\n"))
    return "\n".join(line for line in lines if line)


def from_plain(value: str) -> str:
    """Plain text as HTML, one paragraph per line."""
    lines = (line.strip() for line in value.split("\n"))
    return "".join(f"<p>{html.escape(line, quote=False)}</p>" for line in lines if line)
