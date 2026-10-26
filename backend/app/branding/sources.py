"""Read trusted employer page seeds from the existing source catalog.

No domain is guessed from a name. Feed-only and external application URLs are
not evidence that a site belongs to an employer. Source/job identities stay intact.
"""
from dataclasses import dataclass
import hashlib
import json
from urllib.parse import quote, urlsplit, urlunsplit

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from backend.app.db.models import JobRecord, JobSourceRecord
from backend.app.scheduling.types import SourceType


@dataclass(frozen=True)
class LogoPage:
    url: str
    employer_owned: bool = False


@dataclass(frozen=True)
class LogoSeed:
    company: str
    identity: str
    pages: tuple[LogoPage, ...]


BOARD_URLS = {
    "greenhouse": "https://job-boards.greenhouse.io/{account}",
    "lever": "https://jobs.lever.co/{account}",
    "ashby": "https://jobs.ashbyhq.com/{account}",
    "smartrecruiters": "https://careers.smartrecruiters.com/{account}",
    "workable": "https://apply.workable.com/{account}",
    "gem": "https://jobs.gem.com/{account}",
}
EMPLOYER_SITES = frozenset({
    "amazon", "apple", "google", "ibm", "atlassian", "shopify",
    "bytedance", "jobposting_sitemap", "jibe", "eightfold", "eightfold_pcsx",
})
SHARED_HOSTS = (
    "myworkdayjobs.com", "myworkdaysite.com", "greenhouse.io", "greenhouse.com",
    "lever.co", "ashbyhq.com", "smartrecruiters.com", "workable.com",
    "oraclecloud.com", "icims.com", "jibe.com", "jibeapply.com", "eightfold.ai",
    "jobvite.com", "taleo.net", "applytojob.com", "breezy.hr", "gem.com",
    "personio.de", "personio.com", "dayforcehcm.com", "successfactors.com",
    "successfactors.eu", "ultipro.com", "adp.com",
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "wikipedia.org", "wikidata.org", "youtube.com", "crunchbase.com",
    "github.com", "gitlab.com",
)


def shared_host(host: str) -> bool:
    return any(host == suffix or host.endswith("." + suffix) for suffix in SHARED_HOSTS)


def _page(url: str, *, employer_owned: bool = False) -> LogoPage | None:
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.port not in (None, 443)):
            return None
        # Tracking parameters are unnecessary for public employer identity.
        return LogoPage(urlunsplit(("https", parsed.netloc, parsed.path or "/", "", "")),
                        employer_owned and not shared_host(parsed.hostname.lower()))
    except ValueError:
        return None


def company_logo_seed(session: Session, company: str) -> LogoSeed:
    sources = session.scalars(select(JobSourceRecord).where(
        JobSourceRecord.company_name == company, JobSourceRecord.enabled.is_(True),
        JobSourceRecord.source_type.in_([kind.value for kind in SourceType if kind.value not in ("simplify", "ripplematch")]),
    ).order_by(JobSourceRecord.id).limit(6)).all()
    by_identity = {(s.source_type, s.source_account): s for s in sources}
    # Exact, indexed company lookup. Do not scan the job corpus with lower() or
    # fetch a logo for an arbitrary query URL supplied by the browser.
    jobs = session.execute(select(JobRecord.source, JobRecord.source_account, JobRecord.official_url)
        .where(JobRecord.company == company,
               tuple_(JobRecord.source, JobRecord.source_account).in_(by_identity))
        .order_by(JobRecord.id.desc()).limit(12)).all() if sources else []
    pages: list[LogoPage] = []
    matched = set()
    for kind, account, url in jobs:
        source = by_identity.get((kind, account))
        if source is None or (kind, account) in matched:
            continue
        configured = source.source_host or account.split("/", 1)[0]
        configured = configured.lower().removeprefix("https://").split("/", 1)[0]
        try:
            owned = kind in EMPLOYER_SITES and urlsplit(url).hostname == configured
        except ValueError:
            continue
        page = _page(url, employer_owned=owned)
        if page and page not in pages:
            matched.add((kind, account))
            pages.append(page)
    for source in sources:
        if source.last_verified_at is None and (source.source_type, source.source_account) not in matched:
            continue
        template = BOARD_URLS.get(source.source_type)
        if template:
            page = _page(template.format(account=quote(source.source_account, safe="")))
            if page and page not in pages:
                pages.append(page)
    # A root favicon is considered only on an employer-owned, registered host.
    for page in tuple(pages):
        if page.employer_owned:
            root = _page(urlunsplit((*urlsplit(page.url)[:2], "/", "", "")), employer_owned=True)
            if root and root not in pages:
                pages.append(root)
    identities = sorted((s.source_type, s.source_account, s.source_host or "",
                         (s.source_type, s.source_account) in matched) for s in sources)
    # Parser revisions must not keep serving a six-hour miss from older code.
    identity = hashlib.sha256(json.dumps(["tenant-branding-v4", company, identities], ensure_ascii=True).encode()).hexdigest()
    return LogoSeed(company, identity, tuple(pages[:4]))
