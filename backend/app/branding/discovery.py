"""Extract employer-declared assets, without using ATS branding as a fallback."""
from dataclasses import dataclass
from html.parser import HTMLParser
import io
import json
import re
import time
import unicodedata
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

from PIL import Image, UnidentifiedImageError

from backend.app.branding.sources import LogoPage, LogoSeed, shared_host
from backend.app.branding.transport import LogoUnavailable, Refused, checked_url


@dataclass(frozen=True)
class LogoAsset:
    png: bytes
    source: str
    evidence: str
    fetched_at: float


def normalized(value):
    return re.sub(r"\s+", " ", re.sub(r"[.,®™]", "", unicodedata.normalize("NFKC", value).casefold())).strip()


class BrandingHTML(HTMLParser):
    def __init__(self, company, page_url=""):
        super().__init__(convert_charrefs=True)
        self.company = normalized(company)
        self.icons, self.logos, self.organizations = [], [], []
        self.script, self.text = False, []
        self.page_url = page_url
        page = urlsplit(page_url)
        self.lever = page.hostname == "jobs.lever.co" and bool(page.path.strip("/"))
        self.workday = bool(re.fullmatch(r"[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com", page.hostname or ""))
        self.greenhouse = page.hostname in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and bool(page.path.strip("/"))
        self.oracle = bool(re.fullmatch(r"[a-z0-9-]+\.fa\.ocs\.oraclecloud\.com", page.hostname or "")
                           and re.match(r"^/hcmUI/CandidateExperience/[^/]+/sites/[^/]+(?:/|$)", page.path))
        self.oracle_site = None
        self.websites = []
        self.tenant_header = False

    def greenhouse_logo(self, value):
        image = urlsplit(urljoin(self.page_url, value))
        return bool(self.greenhouse and image.scheme == "https" and not image.fragment
                    and re.fullmatch(r"(?:s\d+-)?recruiting\.cdn\.greenhouse\.io", image.hostname or "")
                    and re.fullmatch(r"/external_greenhouse_job_boards/logos/[^\s]+", image.path))

    def oracle_icon(self, value):
        page, image = urlsplit(self.page_url), urlsplit(urljoin(self.page_url, value))
        query = parse_qs(image.query, keep_blank_values=True)
        return bool(self.oracle and self.oracle_site and image.scheme == "https"
                    and image.netloc == page.netloc and not image.fragment
                    and re.fullmatch(r"/hcmRestApi/CandidateExperience/siteFavicon/favicon-\d+x\d+\.png", image.path)
                    and query.get("siteNumber") == [self.oracle_site]
                    and set(query) <= {"siteNumber", "size"})

    def tenant_meta_logo(self, value):
        # Workday's social image is its tenant's dedicated branding endpoint,
        # not a generic preview image. Require the same host and site path.
        page, image = urlsplit(self.page_url), urlsplit(urljoin(self.page_url, value))
        site = page.path.strip("/").split("/", 1)[0]
        workday = (self.workday and bool(site) and image.scheme == "https"
                and image.netloc == page.netloc
                and image.path == f"/{site}/assets/logo"
                and not image.query and not image.fragment)
        # These paths explicitly identify tenant branding, rather than a job
        # thumbnail or the hosting platform's own favicon. The page itself
        # already comes from this employer's registered board identity.
        ashby = (page.hostname == "jobs.ashbyhq.com" and bool(site)
                 and image.hostname == "app.ashbyhq.com"
                 and re.fullmatch(r"/api/images/org-theme-logo/[a-f0-9-]+/[a-f0-9-]+/[a-f0-9-]+\.(png|jpe?g|webp)", image.path))
        workable = (page.hostname == "apply.workable.com" and bool(site)
                    and image.hostname == "workablehr.s3.amazonaws.com"
                    and re.fullmatch(r"/uploads/account/open_graph_logo/\d+/social", image.path))
        return bool(workday or self.greenhouse_logo(value)
                    or image.scheme == "https" and not image.fragment and (ashby or workable))

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.oracle and re.fullmatch(r"[A-Za-z0-9_-]+", a.get("data-sitenumber") or ""):
            self.oracle_site = a["data-sitenumber"]
        if tag == "a":
            self.tenant_header = self.lever and "main-header-logo" in (a.get("class") or "").split()
        if tag == "meta" and (a.get("property") or a.get("name")) in {"og:image", "twitter:image"}:
            candidate = a.get("content") or ""
            if self.tenant_meta_logo(candidate):
                self.logos.append(candidate)
        if tag == "link" and ("icon" in (a.get("rel") or "").lower().split() or a.get("rel") == "apple-touch-icon"):
            self.icons.append(a.get("href", ""))
        if tag == "img":
            alt = normalized(a.get("alt") or "")
            marker = normalized((a.get("id") or "") + " " + (a.get("class") or ""))
            employer_alt = normalized(re.sub(r"\blogo\b", "", alt)) == self.company
            # Generic employer-logo markers belong to this verified tenant.
            # A provider-specific logo or generic og:image is never accepted.
            generic = alt in ("company logo", "employer logo") or (not alt and marker.strip() in ("company-logo", "employer-logo"))
            greenhouse = self.greenhouse_logo(a.get("src") or "")
            # Lever's dedicated employer header remains the tenant's mark if
            # it rebrands. Do not accept its footer/provider or generic og:image.
            if employer_alt or generic or self.tenant_header or greenhouse:
                self.logos.append(a.get("src", ""))
        if tag == "script":
            self.script = "organization" if (a.get("type") or "").lower() == "application/ld+json" else "tenant" if self.greenhouse else False
            self.text = []

    def handle_data(self, data):
        if self.script:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "a":
            self.tenant_header = False
        if tag == "script" and self.script:
            kind = self.script
            self.script = False
            try:
                body = "".join(self.text).strip()
                if kind == "organization":
                    self._organization(json.loads(body), 0)
                elif body.startswith("window.__remixContext = "):
                    # Parse data only, never execute the board's JavaScript.
                    context, _ = json.JSONDecoder().raw_decode(body.split("=", 1)[1].lstrip())
                    logo = context["state"]["loaderData"]["root"]["boardConfiguration"]["logo"]
                    if not isinstance(logo, dict):
                        return
                    if isinstance(logo.get("url"), str) and self.greenhouse_logo(logo["url"]):
                        self.logos.append(logo["url"])
                    website = logo.get("href")
                    if isinstance(website, str):
                        parts = urlsplit(website)
                        # Legacy tenant settings can declare HTTP. Contact only
                        # the same declared host/path over validated HTTPS.
                        if parts.scheme == "http":
                            website = urlunsplit(("https", *parts[1:]))
                        checked_url(website)
                        if not shared_host(urlsplit(website).hostname or ""):
                            self.websites.append(website)
            except (ValueError, RecursionError, KeyError, TypeError, LogoUnavailable):
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
            try:
                result = fetch(page.url, 800_000, deadline)
            except Refused:
                raise
            except (LogoUnavailable, OSError):
                continue
            if result.status != 200 or "html" not in result.content_type.lower():
                continue
            parser = BrandingHTML(seed.company, result.url)
            parser.feed(result.data.decode("utf-8", "replace"))
            candidates = list(parser.logos)
            for website in parser.websites:
                pages.insert(index + 1, LogoPage(website, True))
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
            # A registered board can redirect to the employer's own posting.
            # Its exact hiringOrganization is independent identity evidence;
            # the ATS adapter's source type need not own that resulting host.
            if (page.employer_owned or parser.organizations) and not shared_host(urlsplit(result.url).hostname or ""):
                candidates += parser.icons
            if page.employer_owned and not shared_host(urlsplit(result.url).hostname or ""):
                candidates.append(urljoin(result.url, "/favicon.ico"))
            candidates += [icon for icon in reversed(parser.icons) if parser.oracle_icon(icon)]
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
                try:
                    icon = fetch(url, 1_048_576, deadline)
                except Refused:
                    raise
                except (LogoUnavailable, OSError):
                    continue
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
