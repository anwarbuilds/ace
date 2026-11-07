"""Employer identity is evidence about one board, never a fuzzy name join.

An old name leading to a new owner's board proves where to read today. It
does not prove the two legal employers share petition history. Reviewed
petition mappings remain exact and separate from these display decisions.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
import html
import json
import re
import unicodedata


# These are reviewed board facts, not a list of words that make a company
# an investor. Retain the evidence when a board is switched off so a paste
# or another discovery origin cannot accidentally register it again.
REVIEWED_SHARED_BOARDS = {
    ("ashby", "pear-vc"): (
        "Shared portfolio board, not one employer. Reviewed 2026-10-30; "
        "https://jobs.ashbyhq.com/pear-vc"
    ),
}

UNVERIFIED_SOURCE_MARKER = 'identity_unverified'


def registration_origin(origin: str, identity_state: str) -> str:
    """Retain uncertainty across processes without creating a legal alias."""
    return f'{origin} {UNVERIFIED_SOURCE_MARKER}' if identity_state == 'unverified' else origin

_LEGAL_SUFFIX = re.compile(r"(?:\s+(?:inc|incorporated|llc|ltd|limited|corp|corporation|pbc))+$")
_TLD = re.compile(r"\.(?:com|ai|io|co|dev|org|net|app|tech|xyz)$", re.I)
_FIRM = re.compile(r"\b(?:vc|ventures?|capital|partners|portfolio|talent\s+network)\b", re.I)
_PORTFOLIO = re.compile(
    r"\b(?:portfolio\s+(?:company\s+)?(?:jobs|careers|opportunities)|"
    r"jobs\s+(?:at|across|in)\s+(?:our\s+|the\s+)?portfolio\s+companies|"
    r"careers\s+at\s+our\s+portfolio\s+companies)\b", re.I,
)


def name_keys(name: str | None) -> frozenset[str]:
    """Punctuation and legal endings only; retain Labs, AI and subsidiaries.

    No substring, shared-word, initials or parent-company inference. Domain
    spellings are accepted only when they reduce to the same whole name.
    """
    value = unicodedata.normalize("NFKC", name or "").casefold().strip()
    keys = set()
    for spelling in (value, _TLD.sub("", value)):
        words = re.sub(r"[^\w]+", " ", spelling, flags=re.UNICODE).strip()
        words = _LEGAL_SUFFIX.sub("", words).strip()
        if words:
            keys.add(words.replace(" ", ""))
    return frozenset(keys)


def same_employer(first: str | None, second: str | None) -> bool:
    return bool(name_keys(first) & name_keys(second))


def shared_board_reason(source_type: str, account: str) -> str | None:
    return REVIEWED_SHARED_BOARDS.get((source_type.casefold(), account.strip().casefold()))


def portfolio_name_hints(titles: Iterable[str], owner: str) -> tuple[str, ...]:
    """Unverified search leads from a board already reviewed as shared.

    A suffix can be a company, team or location. It never sets a job's
    employer or authorizes a source; the existing name search must verify it.
    """
    hints = set()
    noise = re.compile(r"\b(?:remote|hybrid|onsite|frontend|backend|full\s*stack|engineer|engineering|developer|intern|india|usa|united states)\b", re.I)
    for title in titles:
        parts = re.split(r"\s+[-\u2013\u2014]\s+", title)
        if len(parts) < 2:
            continue
        hint = re.sub(r"\s*\([^)]*\)\s*$", "", parts[-1]).strip()
        if 2 <= len(hint) <= 100 and "," not in hint and not noise.search(hint) and not same_employer(hint, owner):
            hints.add(hint)
    return tuple(sorted(hints))


@dataclass(frozen=True, slots=True)
class BoardEvidence:
    owner: str | None = None
    employers: tuple[str, ...] = ()
    shared: bool = False
    basis: str = ""
    unavailable: bool = False


@dataclass(frozen=True, slots=True)
class EmployerIdentity:
    company: str | None
    state: str
    reason: str


def posting_employers(jobs: Iterable) -> tuple[str, ...]:
    """Only structured employer fields, never description mentions or titles."""
    names = []
    for job in jobs:
        if not isinstance(job, dict):
            names.extend(name.strip() for name in getattr(job, 'hiring_organizations', ())
                         if isinstance(name, str) and name.strip())
            continue
        for field in ("hiringOrganization", "company"):
            organization = job.get(field)
            if isinstance(organization, dict):
                name = organization.get("name")
                if isinstance(name, str) and name.strip():
                    names.append(name.strip())
    return tuple(dict.fromkeys(names))


def page_evidence(page: str, owner: str | None, *, basis: str) -> BoardEvidence:
    """Read explicit portfolio headings and JobPosting hiring organizations.

    Description prose is deliberately excluded: a real employer can mention
    its investment portfolio or a customer's name in an ordinary job.
    """
    headings = re.findall(r"<(?:title|h1|h2)\b[^>]*>(.*?)</(?:title|h1|h2)>", page, re.I | re.S)
    shared = any(_PORTFOLIO.search(html.unescape(re.sub(r"<[^>]+>", " ", s))) for s in headings)
    jobs = []
    for raw in re.findall(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page, re.I | re.S):
        try:
            nodes = json.loads(raw)
        except (ValueError, TypeError):
            continue
        pending = nodes if isinstance(nodes, list) else [nodes]
        while pending:
            node = pending.pop()
            if not isinstance(node, dict):
                continue
            kind = node.get("@type", "")
            if kind == "JobPosting" or isinstance(kind, list) and "JobPosting" in kind:
                jobs.append(node)
            graph = node.get("@graph")
            if isinstance(graph, list):
                pending.extend(graph)
    return BoardEvidence(owner, posting_employers(jobs), shared, basis)


def resolve_employer(
    listed: str,
    evidence: BoardEvidence | str | None,
    *,
    source_type: str = "",
    account: str = "",
    titles: Sequence[str] = (),
) -> EmployerIdentity:
    reviewed = shared_board_reason(source_type, account)
    if reviewed:
        return EmployerIdentity(None, "shared", reviewed)
    if not isinstance(evidence, BoardEvidence):
        evidence = BoardEvidence(owner=evidence)
    if evidence.shared:
        return EmployerIdentity(None, "shared", "The board lists portfolio companies' jobs, not one employer.")
    if evidence.unavailable:
        return EmployerIdentity(None, "unknown", "ACE could not read the evidence to confirm this board's owner. Kept as a lead.")
    employers: list[str] = []
    for name in evidence.employers:
        if name_keys(name) and not any(same_employer(name, known) for known in employers):
            employers.append(name)
    if len(employers) > 1:
        return EmployerIdentity(None, "shared", "The board names more than one hiring employer.")
    owner = html.unescape(evidence.owner or (employers[0] if employers else "")).strip()
    if not name_keys(owner):
        return EmployerIdentity(None, "unknown", "ACE could not confirm who owns this board. Kept as a lead.")
    if employers and not same_employer(owner, employers[0]):
        return EmployerIdentity(None, "unknown", "The board name and hiring employer disagree. Kept as a lead.")
    # Titles can raise uncertainty, never assign an employer or a legal alias.
    # This catches agreeing investor labels without calling every Capital
    # company a shared board. Structured hiring-organization evidence wins.
    if _FIRM.search(owner) and not employers:
        tails = {re.split(r"\s+[-\u2013\u2014]\s+", title)[-1].strip().casefold()
                 for title in titles if re.search(r"\s+[-\u2013\u2014]\s+", title)}
        tails -= {"remote", "hybrid", "onsite", "on site", "us", "usa", "united states"}
        if len(tails) > 1 or not same_employer(listed, owner):
            return EmployerIdentity(None, "unknown", "This may be a shared investor board. ACE needs employer evidence.")
    company = listed.strip() if same_employer(listed, owner) else owner
    return EmployerIdentity(company, "confirmed", evidence.basis or "The board names its owner.")


def registration_identity(listed, evidence, *, source_type, account, jobs=(),
                          source_host=None, direct=False, listed_names=()):
    """A readable exact board can be monitored without inventing its owner.

    Name guessing remains strict. This is only for boards already named by
    a feed, a collected link, or a pasted board URL. Contradictory evidence,
    reviewed/shared findings and failed identity reads always stop additions.
    Silence on a provider with no owner metadata is not a permanent refusal.
    """
    from backend.app.coverage.companies import MULTI_EMPLOYER_SOURCES
    if source_type in MULTI_EMPLOYER_SOURCES:
        return EmployerIdentity(None, 'shared', 'This is a multi-employer feed, not one employer board.')
    if not isinstance(evidence, BoardEvidence):
        evidence = BoardEvidence(owner=evidence)
    evidence = replace(evidence, employers=tuple(dict.fromkeys(
        (*evidence.employers, *posting_employers(jobs)))))
    titles = [job.get('title') or job.get('name') or '' if isinstance(job, dict)
              else getattr(job, 'title', '') for job in jobs]
    result = resolve_employer(listed, evidence, source_type=source_type,
                              account=account, titles=titles)
    if result.company is not None:
        # A pasted board token is an address, not a competing employer claim.
        if not direct and any(not same_employer(name, result.company)
                              for name in (listed_names or (listed,))):
            return EmployerIdentity(None, 'unknown', 'The listed company and board owner disagree. Kept as a lead.')
        return result
    if (evidence.owner or evidence.employers or evidence.shared or evidence.unavailable
            or shared_board_reason(source_type, account)):
        return result
    if any(not same_employer(listed, name) for name in listed_names):
        return EmployerIdentity(None, 'unknown', 'The feed names different employers for this board. Kept as a lead.')
    if source_type == 'workday':
        from backend.app.coverage.probing import workday_belongs_to
        from backend.app.coverage.companies import is_namesake
        tenant = account.partition('/')[0].casefold()
        if source_host and not re.fullmatch(re.escape(tenant) + r'\.wd\d+\.myworkdayjobs\.com', source_host.casefold()):
            return EmployerIdentity(None, 'unknown', 'The Workday tenant and board address disagree. Kept as a lead.')
        binding = workday_belongs_to(company=listed, token=account)
        if binding:
            return EmployerIdentity(listed, 'confirmed', binding)
        # The vendor's own board is a known wrong destination from customer
        # careers pages. A shortened employer tenant, however, is silence
        # about ownership, not evidence that it belongs to another company.
        # Keep name searches strict; only an already-read exact address may
        # fall through as unverified, without any sponsorship inheritance.
        if not source_host or tenant == 'workday' or is_namesake(source_type, account):
            return result
    if source_type in ('greenhouse', 'ashby', 'lever'):
        # These providers publish owner metadata; do not rescue a failed
        # name search or customer mention with the token it started from.
        return result
    return EmployerIdentity(listed, 'unverified',
        'The link names a readable board. Its employer name is not independently confirmed.')


def read_board_evidence(source_type: str, account: str, *, source_host=None, fetch=None, fetch_text=None, jobs=()) -> BoardEvidence:
    """Use the existing reader addresses; callers provide polite fetchers."""
    from backend.app.coverage.probing import (
        _fetch_json, _fetch_text, board_metadata_name, board_page_name, BOARD_PAGE_URLS,
    )
    if shared_board_reason(source_type, account):
        return BoardEvidence(shared=True, basis=shared_board_reason(source_type, account) or "")
    if source_type == "greenhouse":
        owner = board_metadata_name(source_type=source_type, token=account, fetch=fetch or _fetch_json)
        return BoardEvidence(owner=owner, employers=posting_employers(jobs), basis="The board's own metadata.")
    pages = {**BOARD_PAGE_URLS, 'workable': 'https://apply.workable.com/{token}/',
             'gem': 'https://jobs.gem.com/{token}'}
    if source_type in pages:
        template = pages[source_type]
        if source_type == "lever" and source_host == "jobs.eu.lever.co":
            template = "https://jobs.eu.lever.co/{token}"
        page = (fetch_text or _fetch_text)(template.format(token=account))
        if source_type in BOARD_PAGE_URLS:
            owner = board_page_name(source_type=source_type, token=account, fetch_text=lambda url: page)
        else:
            match = re.search(r'<title[^>]*>([^<]{1,160})', page, re.I)
            owner = html.unescape(match.group(1)).strip() if match else ''
            owner = re.sub(r'\s*[|\-]\s*(?:Workable|Gem)\s*$', '', owner, flags=re.I)
            owner = re.sub(r'\s*[-|]\s*current\s+openings\s*$', '', owner, flags=re.I)
            owner = re.sub(r'^(?:Careers?|Jobs?)\s+(?:at|with)\s+', '', owner, flags=re.I)
            owner = re.sub(r'\b(?:jobs?|careers?|openings?|open roles)\b', ' ', owner, flags=re.I).strip()
            if owner.casefold() in ('', 'workable', 'gem'):
                owner = None
        found = page_evidence(page, owner, basis="The board's own page.")
        return replace(found, employers=tuple(dict.fromkeys((*found.employers, *posting_employers(jobs)))),
                       unavailable=not bool(page))
    return BoardEvidence(employers=posting_employers(jobs), basis="The postings' structured hiring employer.")
