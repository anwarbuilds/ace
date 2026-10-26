"""The email as it was sent, made safe to show inside ACE.

No Gmail access of its own and no database writes. Given a Gmail message
payload, this rebuilds the email's HTML from an allowlist so the owner sees
the real layout, text and links in a sandboxed frame that runs no scripts.
Links open in a new tab. Images attached to the email are shown; images on
the sender's servers are never fetched, so a tracking pixel cannot learn the
email was opened. Dashes become the punctuation they stand for, as
everywhere else in ACE. Nothing produced here is stored.
"""

from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable

# Dropped together with everything inside them.
_DROP = {"script", "noscript", "template", "iframe", "object", "applet", "frameset", "noframes", "svg", "math",
         "video", "audio", "canvas", "title", "button", "select", "textarea", "map", "datalist", "output"}
# Void elements that are simply left out.
_SKIP = {"embed", "frame", "input", "link", "meta", "base", "source", "track", "param", "area", "keygen", "basefont"}
_KEEP = {"a", "abbr", "address", "article", "aside", "b", "bdi", "bdo", "big", "blockquote", "br", "caption", "center",
         "cite", "code", "col", "colgroup", "dd", "del", "details", "dfn", "div", "dl", "dt", "em", "fieldset",
         "figcaption", "figure", "font", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup", "i", "img",
         "ins", "kbd", "label", "legend", "li", "main", "mark", "nav", "ol", "p", "pre", "q", "s", "samp", "section",
         "small", "span", "strike", "strong", "sub", "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead",
         "time", "tr", "tt", "u", "ul", "var", "wbr"}
_VOID = {"br", "col", "img", "wbr"}
_ATTRS = {"align", "alt", "bgcolor", "border", "cellpadding", "cellspacing", "class", "color", "colspan", "datetime",
          "dir", "face", "headers", "height", "id", "lang", "nowrap", "open", "reversed", "role", "rowspan", "scope",
          "size", "span", "start", "style", "summary", "title", "type", "valign", "width"}
_SCHEMES = ("http://", "https://", "mailto:", "tel:")
_IMAGE_TYPES = ("image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp")
_DATA_IMAGE = re.compile(r"(?i)^data:image/(?:png|jpe?g|gif|webp);base64,[a-z0-9+/=\s]+$")
_CSS_URL = re.compile(r"(?i)url\s*\(\s*(['\"]?)(.*?)\1\s*\)", re.S)
_CSS_BAD = re.compile(r"(?i)@import[^;]*;?|expression\s*\(|behaviou?r\s*:|-moz-binding|javascript:")
_URL = re.compile(r"https?://[^\s<>\"']+")
# Dashes. Em dash and horizontal bar are punctuation; an en dash, figure dash
# or hyphen with a space on each side is one too ("Wayfern - Engineer"). An en
# dash joining two numbers or words, as in a range of hours, reads as "to". A
# line drawn from dash-like characters is a rule, not text. Hyphens inside
# words are untouched.
_EM = re.compile(r"[ \t\u00a0]*[\u2014\u2015]+[ \t\u00a0]*")
_SPACED = re.compile(r"(?<=\S)[ \t\u00a0]+[\u2012\u2013-][ \t\u00a0]+(?=\S)")
_RANGE = re.compile(r"(?<=\w)\u2013(?=\w)")
_BULLET = re.compile(r"(?m)^([ \t]*)[-*\u2012\u2013][ \t]+(?=\S)")
# Inside HTML a run of text can start mid-line, right after a bold word.
_LEAD = re.compile(r"^[ \t\u00a0]+[-\u2012\u2013\u2014\u2015][ \t\u00a0]+(?=\S)")
_RULE = re.compile(r"^[\s_=~*\u2010-\u2015\u2212-]{3,}$")
_IMAGE_LIMIT = 10
_IMAGE_CHARS = 1_500_000
_TOTAL_IMAGE_CHARS = 5_000_000
_HTML_LIMIT = 2_000_000

FRAME_POLICY = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:"
_FRAME_CSS = (
    "html{color-scheme:light}"
    "body{margin:0;padding:20px 22px;background:#fff;color:#202124;font:14px/1.55 Arial,Helvetica,sans-serif;"
    "overflow-wrap:anywhere}"
    "img{max-width:100%;height:auto}table{max-width:100%}a{color:#1a56c4}pre{white-space:pre-wrap}"
    ".ace-plain{white-space:pre-wrap}.ace-alt{color:#5f6368;font-style:italic}.ace-gap{height:14px}"
)


@dataclass(frozen=True)
class Shown:
    document: str  # A complete HTML document for an iframe's srcdoc.
    kind: str  # "html" or "text": which version of the email it shows.
    blocked_images: int  # Images on the sender's servers that were not loaded.


def decode(part: dict, fetch: Callable[[str], str] | None = None) -> str:
    """One MIME part's text in its declared charset, or empty."""
    body = part.get("body") or {}
    encoded = body.get("data", "")
    if not encoded and fetch and body.get("attachmentId"):
        encoded = fetch(str(body["attachmentId"]))  # Gmail keeps large bodies apart.
    content_type = next((str(h.get("value", "")) for h in part.get("headers", []) if str(h.get("name", "")).casefold() == "content-type"), "")
    charset = re.search(r'(?i)charset="?([\w.-]+)', content_type)
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (ValueError, TypeError):
        return ""
    try:
        return raw.decode(charset.group(1) if charset else "utf-8", "replace")
    except LookupError:
        return raw.decode("utf-8", "replace")


def parts(payload: dict, mime: str) -> list[dict]:
    """Every leaf part of one MIME type, in message order."""
    if payload.get("mimeType") == mime:
        return [payload]
    return [found for part in payload.get("parts", []) if isinstance(part, dict) for found in parts(part, mime)]


def tidy(text: str, inline: bool = False) -> str:
    """Text with dashes turned into the punctuation they stand for.

    ``inline`` is for a run of text inside HTML, which may follow other text
    on the same line ("<b>Role</b> - Engineer"), so a dash it opens with is a
    separator, not a bullet.
    """
    if inline:
        text = _LEAD.sub(", ", text)

    def em(match: re.Match) -> str:
        start, end = match.start(), match.end()
        if (start and text[start - 1] == "\n") or (not start and match.group(0)[:1] not in " \t\u00a0"):
            return ""  # A dash opening a line or a text run.
        return " " if end == len(text) or text[end] == "\n" else ", "

    def spaced(match: re.Match) -> str:
        end = match.end()
        between_numbers = text[match.start() - 1].isdigit() and end < len(text) and text[end].isdigit()
        return " to " if between_numbers else ", "

    text = _BULLET.sub(lambda match: match.group(1) + "\u2022 ", text)
    text = _EM.sub(em, text)
    text = _RANGE.sub(" to ", text)
    return _SPACED.sub(spaced, text)


def _css(value: str) -> str:
    def url(match: re.Match) -> str:
        return match.group(0) if _DATA_IMAGE.match(match.group(2).strip()) else "none"
    return _CSS_BAD.sub("", _CSS_URL.sub(url, value)).replace("</", "")


def _attribute(name: str, value: str) -> str:
    return f' {name}="{html.escape(value, quote=True)}"'


class _Rebuild(HTMLParser):
    def __init__(self, images: dict[str, str]) -> None:
        super().__init__(convert_charrefs=True)
        self.images = images
        self.out: list[str] = []
        self.dropping: str | None = None
        self.depth = 0
        self.blocked = 0

    def _start(self, tag: str, attrs: list[tuple[str, str | None]], closed: bool) -> None:
        if self.dropping:
            if tag == self.dropping and not closed:
                self.depth += 1
            return
        if tag in _DROP:
            if not closed:  # A self-closed <svg/> has nothing inside to drop.
                self.dropping, self.depth = tag, 1
            return
        if tag == "style":
            self.out.append("<style>")  # Its text is cleaned in handle_data.
            return
        if tag in _SKIP or tag in {"html", "head", "form", "picture"}:
            return
        if tag == "hr":
            self.out.append('<div class="ace-gap"></div>')  # A drawn rule is spacing, never a line.
            return
        if tag == "body":
            tag, attrs = "div", [*attrs, ("class", "ace-body")]
        elif tag not in _KEEP:
            return  # Unknown wrappers (Outlook's o:p and others) keep their content.
        values = {name: value or "" for name, value in attrs}
        kept: list[str] = []
        if tag == "img":
            source = values.get("src", "").strip()
            if source.casefold().startswith("cid:"):
                source = self.images.get(source[4:].strip("<> ").casefold(), "")
            elif not _DATA_IMAGE.match(source):
                source = ""
            if not source:
                # A 1 by 1 tracking pixel is invisible anyway; anything else is a
                # picture the owner should know was left out.
                if not {values.get("width", "").strip().lower(), values.get("height", "").strip().lower()} <= {"0", "1", "0px", "1px"}:
                    self.blocked += 1
                alt = tidy(values.get("alt", "")).strip()
                if alt:
                    self.out.append(f'<span class="ace-alt">{html.escape(alt, quote=False)}</span>')
                return
            kept.append(_attribute("src", source))
        if tag == "a":
            link = re.sub(r"[\x00-\x20]+", "", values.get("href", ""))
            if link.startswith("#"):
                kept.append(_attribute("href", link))
            elif link.casefold().startswith(_SCHEMES):
                kept.append(_attribute("href", link) + ' target="_blank" rel="noopener noreferrer"')
        for name, value in values.items():
            if not (name in _ATTRS or name.startswith("aria-")):
                continue
            if name == "style":
                value = _css(value)
            elif name in {"title", "alt", "aria-label"}:
                value = tidy(value)
            kept.append(_attribute(name, value))
        self.out.append(f"<{tag}{''.join(kept)}>")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, True)

    def handle_endtag(self, tag: str) -> None:
        if self.dropping:
            if tag == self.dropping:
                self.depth -= 1
                if not self.depth:
                    self.dropping = None
            return
        if tag in {"body", "style"}:
            self.out.append("</div>" if tag == "body" else "</style>")
        elif tag in _KEEP and tag not in _VOID:
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self.dropping:
            return
        if self.cdata_elem == "style":
            self.out.append(_css(data))
            return
        bare = data.strip()
        if re.fullmatch(r"[\u2012\u2013\u2014\u2015-]", bare):
            # A lone dash between two inline pieces of text, or a placeholder.
            self.out.append(", " if data[:1].isspace() and data[-1:].isspace() else "")
            return
        if bare and _RULE.match(bare):
            return
        self.out.append(html.escape(tidy(data, inline=True), quote=False))

    def handle_comment(self, data: str) -> None:
        return  # Outlook-only conditional HTML and notes stay hidden.

    def handle_decl(self, decl: str) -> None:
        return

    def unknown_decl(self, data: str) -> None:
        return


def _inline_images(payload: dict, markup: str, fetch: Callable[[str], str] | None) -> dict[str, str]:
    """Images attached to the email itself, by Content-ID, as data URLs."""
    wanted = {match.casefold() for match in re.findall(r"(?i)cid:([^\"'\s>)]+)", markup)}
    found: dict[str, str] = {}
    total = 0

    def walk(part: dict) -> None:
        nonlocal total
        for child in part.get("parts", []) or []:
            if isinstance(child, dict):
                walk(child)
        mime = str(part.get("mimeType", "")).casefold()
        headers = {str(h.get("name", "")).casefold(): str(h.get("value", "")) for h in part.get("headers", [])}
        cid = headers.get("content-id", "").strip().strip("<>").casefold()
        if not cid or cid not in wanted or mime not in _IMAGE_TYPES or len(found) >= _IMAGE_LIMIT:
            return
        body = part.get("body") or {}
        data = body.get("data") or (fetch(str(body["attachmentId"])) if fetch and body.get("attachmentId") else "")
        if not data or len(data) > _IMAGE_CHARS or total + len(data) > _TOTAL_IMAGE_CHARS:
            return
        total += len(data)
        standard = data.replace("-", "+").replace("_", "/")
        found[cid] = f"data:{'image/jpeg' if mime == 'image/jpg' else mime};base64,{standard}{'=' * (-len(standard) % 4)}"

    if wanted:
        walk(payload)
    return found


def _document(content: str) -> str:
    return ('<!doctype html><html><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{FRAME_POLICY}">'
            '<meta name="referrer" content="no-referrer">'
            f"<style>{_FRAME_CSS}</style></head><body>{content}</body></html>")


def plain_document(text: str) -> str:
    """A plain-text email as a page: its lines kept, its web addresses linked."""
    lines = ["" if _RULE.match(line.strip()) and line.strip() else line for line in text.splitlines()]
    text = tidy("\n".join(lines)).strip()
    pieces: list[str] = []
    done = 0
    for match in _URL.finditer(text):
        url = match.group(0).rstrip(".,;:!?)")  # Sentence punctuation after an address.
        pieces.append(html.escape(text[done:match.start()], quote=False))
        pieces.append(f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(url, quote=False)}</a>')
        done = match.start() + len(url)
    pieces.append(html.escape(text[done:], quote=False))
    return _document(f'<div class="ace-plain">{"".join(pieces)}</div>')


def show(payload: dict, fetch: Callable[[str], str] | None = None, fallback: str = "") -> Shown:
    """The email's HTML version when it has one (what Gmail shows), else its text."""
    markup = "\n".join(decode(part, fetch) for part in parts(payload, "text/html"))[:_HTML_LIMIT]
    text = "\n".join(decode(part, fetch) for part in parts(payload, "text/plain")) or fallback
    if markup.strip():
        parser = _Rebuild(_inline_images(payload, markup, fetch))
        parser.feed(markup)
        parser.close()
        content = "".join(parser.out)
        visible = re.sub(r"<[^>]*>", "", re.sub(r"(?is)<style>.*?</style>", "", content))
        # A malformed email that rebuilds to nothing is shown as its text.
        if visible.strip() or not text.strip():
            return Shown(_document(content), "html", parser.blocked)
    return Shown(plain_document(text), "text", 0)
