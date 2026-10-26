"""Extract employer-declared assets, without using ATS branding as a fallback."""
from dataclasses import dataclass
from html.parser import HTMLParser
import io
import json
import re
import time
import unicodedata
from urllib.parse import urljoin, urlsplit

from PIL import Image, UnidentifiedImageError

from backend.app.branding.sources import LogoPage, LogoSeed, shared_host
from backend.app.branding.transport import LogoUnavailable, checked_url


@dataclass(frozen=True)
class LogoAsset:
    png: bytes
    source: str
    evidence: str
    fetched_at: float


def normalized(value):
    return re.sub(r"\s+", " ", re.sub(r"[.,®™]", "", unicodedata.normalize("NFKC", value).casefold())).strip()


class BrandingHTML(HTMLParser):
    def __init__(self, company):
        super().__init__(convert_charrefs=True)
        self.company = normalized(company)
        self.icons, self.logos, self.organizations = [], [], []
        self.script, self.text = False, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link" and ("icon" in (a.get("rel") or "").lower().split() or a.get("rel") == "apple-touch-icon"):
            self.icons.append(a.get("href", ""))
        if tag == "img":
            alt = normalized(a.get("alt") or "")
            marker = normalized((a.get("id") or "") + " " + (a.get("class") or ""))
            employer_alt = normalized(re.sub(r"\blogo\b", "", alt)) == self.company
            # Generic employer-logo markers belong to this verified tenant.
            # A provider-specific logo or generic og:image is never accepted.
            generic = alt in ("company logo", "employer logo") or (not alt and marker.strip() in ("company-logo", "employer-logo"))
            if employer_alt or generic:
                self.logos.append(a.get("src", ""))
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self.script, self.text = True, []

    def handle_data(self, data):
        if self.script:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.script:
            self.script = False
            try:
                self._organization(json.loads("".join(self.text)), 0)
            except (ValueError, RecursionError):
                pass

    def _organization(self, value, depth):
        if depth > 12:
            return
        if isinstance(value, list):
            for row in value[:100]:
                self._organization(row, depth + 1)
        elif isinstance(value, dict):
            kind = value.get("@type", "")
            if isinstance(kind, str) and kind in ("Organization", "Corporation") and normalized(str(value.get("name", ""))) == self.company:
                self.organizations.append(value)
            # hiringOrganization may omit @type, as permitted by existing ATS.
            org = value.get("hiringOrganization")
            if isinstance(org, dict) and normalized(str(org.get("name", ""))) == self.company:
                self.organizations.append(org)
            for key, child in list(value.items())[:100]:
                if key != "hiringOrganization":
                    self._organization(child, depth + 1)


def raster_png(data: bytes) -> bytes | None:
    # Decode and re-encode, never serve remote HTML, scripts, SVG or raw files.
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP", "GIF", "ICO", "BMP"}:
                return None
            if min(image.size) < 16 or image.width * image.height > 4_194_304:
                return None
            image.seek(0)
            image.thumbnail((96, 96))
            rgba = image.convert("RGBA")
            extrema = rgba.getextrema()
            if extrema[3][1] == 0 or all(low == high for low, high in extrema):
                return None
            output = io.BytesIO()
            rgba.save(output, format="PNG")
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, EOFError, Image.DecompressionBombError):
        return None


def discover_logo(seed: LogoSeed, fetch) -> LogoAsset | None:
    deadline = time.monotonic() + 12
    visited, images = set(), set()
    pages = list(seed.pages)
    try:
        for index in range(4):
            if index >= len(pages):
                break
            page = pages[index]
            if page.url in visited or time.monotonic() >= deadline:
                continue
            visited.add(page.url)
            result = fetch(page.url, 800_000, deadline)
            if result.status != 200 or "html" not in result.content_type.lower():
                continue
            parser = BrandingHTML(seed.company)
            parser.feed(result.data.decode("utf-8", "replace"))
            candidates = list(parser.logos)
            for org in parser.organizations:
                logo = org.get("logo")
                if isinstance(logo, dict):
                    logo = logo.get("url") or logo.get("contentUrl")
                if isinstance(logo, str):
                    candidates.insert(0, logo)
                website = org.get("sameAs") or org.get("url")
                if isinstance(website, list):
                    website = next((url for url in website if isinstance(url, str) and not shared_host(urlsplit(url).hostname or "")), None)
                if isinstance(website, str) and not shared_host(urlsplit(website).hostname or ""):
                    try:
                        checked_url(website)
                        # Reserve a slot for the employer site explicitly named
                        # by the matched hiringOrganization on its job board.
                        pages.insert(index + 1, LogoPage(website, True))
                    except LogoUnavailable:
                        pass
            if page.employer_owned and not shared_host(urlsplit(result.url).hostname or ""):
                candidates += parser.icons
                candidates.append(urljoin(result.url, "/favicon.ico"))
            for candidate in candidates[:6]:
                if not candidate:
                    continue
                url = urljoin(result.url, candidate)
                if url in images:
                    continue
                images.add(url)
                try:
                    checked_url(url)
                except LogoUnavailable:
                    continue
                icon = fetch(url, 1_048_576, deadline)
                if icon.status != 200:
                    continue
                png = raster_png(icon.data)
                if png:
                    return LogoAsset(png, icon.url, result.url, time.time())
    except (LogoUnavailable, OSError, ValueError, RecursionError):
        # Refusal, timeout, an unsafe redirect or unavailable evidence never
        # affects a job, its eligibility, application status or polling state.
        return None
    return None
