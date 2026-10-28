"""Posting identities from allowlisted ATS URLs; never fetch or follow a link.

Tracking parameters, application tokens and arbitrary numbers are not job IDs.
An identity is scoped to its ATS and employer tenant as well as its posting ID.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlsplit

Posting = tuple[str, str, str]

_ROLE_CLAIMS = (
    re.compile(r"\b(?:for|regarding)\s+(?!(?:your\s+(?:interest|time|application)|applying|taking)\b)(?:(?:the|our|your|a|an)\s+)?([^.!?;\n]{2,160}?)\s+(?:role|position|opening)\b", re.I),
    re.compile(r"\b(?:application|candidacy|applied|applying)\s+(?:for|to)\s+(?:(?:the|our|your|a|an)\s+)?([^.!?;\n]{2,160}?)(?=\s+(?:was|is|has been|at|with|position|role)\b|,\s*(?:we|you|your|and|but|unfortunately|however)\b|[.!?;\n]|$)", re.I),
    re.compile(r"\b(?:job title|position title)\s*:\s*([^.!?;\n]{2,160})", re.I),
    re.compile(r"\b(?:regarding|re|role|position)\s*(?::\s*|\s+)([^.!?;:\n]{2,160})(?=[:.!?;\n]|$)", re.I),
)
_ROLE_WORDS = re.compile(r"\b(?:engineers?|developers?|scientists?|analysts?|interns?|internship|designers?|architects?|researchers?|programmers?|consultants?|specialists?|managers?|engineering)\b", re.I)


def role_claims(text: str) -> tuple[str, ...]:
    claims = []
    for pattern in _ROLE_CLAIMS:
        for match in pattern.finditer(text):
            claim = re.sub(r"^(?:applying|applied)\s+(?:for|to)\s+(?:the\s+)?", "", match[1], flags=re.I).strip()
            if _ROLE_WORDS.search(claim) and claim not in claims:
                claims.append(claim)
    return tuple(claims)


def compatible_role(title: str, claim: str) -> bool:
    # A generic Software Engineer claim can describe a specific storage role;
    # a Storage/Data/Senior claim cannot describe a generic or different role.
    # Keep level, specialty and numerals. Do not equate different role families.
    def tokens(value):
        return set(re.findall(r"[a-z0-9]+", value.casefold())) - {"the", "a", "an", "our", "your", "position", "role", "opening"}
    claimed = tokens(claim)
    return bool(claimed) and claimed <= tokens(title)


def subject_role_claim(subject: str, company_words: str) -> str | None:
    """Keep role modifiers in plain subjects, including untracked specialties.

    Subject wording cannot establish an outcome, but an explicit different role
    can veto an identity. Strip ordinary correspondence labels and the known
    employer, never seniority, specialties, locations or role numerals.
    """
    text = re.sub(r"\b(?:job|req|requisition|reference)\s*(?:id|number|no)?\s*[:#-]?\s*[a-z]{0,4}[-_]?\d[\w-]*", " ", subject, flags=re.I)
    text = " ".join(re.findall(r"[a-z0-9]+", text.casefold()))
    if company_words:
        text = re.sub(r"(?<!\w)"+re.escape(company_words)+r"(?!\w)", " ", text)
        initials = "".join(word[0] for word in company_words.split())
        if len(initials) >= 2:
            text = re.sub(r"\b"+re.escape(initials)+r"\b", " ", text)
    text = re.sub(r"\b(?:re|your|you|we|our|my|the|a|an|for|to|at|with|from|in|on|of|and|regarding|application|candidacy|applications|update|status|notification|thank|thanks|interest|applying|applied|received|submitted|decision|rejected|rejection|interview|invitation|invite|assessment|offer|no|not|position|role|opening)\b", " ", text)
    text = " ".join(text.split())
    return text if _ROLE_WORDS.search(text) else None


def primary_link_text(body: str) -> str:
    """End application-link evidence where recommendations or history begin."""
    return re.split(
        r"(?im)\b(?:unsubscribe|(?:other|similar|recommended) (?:jobs|roles|opportunities)|you may also (?:like|consider)|jobs recommended for you)\b"
        r"|^\s*(?:on .{5,160} wrote:|[- ]*(?:forwarded|original) message[- ]*|from:\s.+$|>.*$)",
        body, maxsplit=1,
    )[0]


def posting_identity(url: str | None) -> Posting | None:
    try:
        p = urlsplit(url or "")
        if p.scheme not in {"https", "http"} or p.username or p.password or p.port not in {None, 80, 443}:
            return None
        host = (p.hostname or "").casefold()
        path = unquote(p.path).strip("/")
        query = parse_qs(p.query)
    except (ValueError, UnicodeError):
        return None
    parts = path.split("/")
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
        if len(parts) >= 3 and parts[1] == "jobs" and parts[2].isdigit():
            return "greenhouse", parts[0].casefold(), parts[2]
        # Embedded boards name the employer separately. A bare global gh_jid
        # on an arbitrary website cannot establish a tenant.
        if path == "embed/job_app" and len(query.get("for", [])) == len(query.get("token", [])) == 1:
            tenant, token = query["for"][0], query["token"][0]
            if re.fullmatch(r"[\w-]+", tenant) and token.isdigit():
                return "greenhouse", tenant.casefold(), token
    if host in {"jobs.lever.co", "jobs.eu.lever.co", "jobs.ashbyhq.com"} and len(parts) in {2, 3}:
        tenant, token = parts[:2]
        if re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", token) and (len(parts) == 2 or parts[2] == "apply"):
            return ("lever-eu" if host == "jobs.eu.lever.co" else "lever" if "lever" in host else "ashby"), tenant.casefold(), token.casefold()
    if host.endswith(".myworkdayjobs.com") or host.endswith(".myworkdaysite.com"):
        # Workday public paths end in title_REQUISITION; the tenant is the
        # first host label, not the regional wdN label or candidate session.
        found = re.search(r"_((?:JR|R)[-_]?\d[\w-]{2,40})(?:/apply)?$", path, re.I)
        tenant = host.split(".")[0]
        if host.endswith(".myworkdaysite.com"):
            if len(parts) < 4 or parts[0] != "recruiting" or not re.fullmatch(r"[a-zA-Z0-9-]+", parts[1]):
                return None
            tenant = parts[1].casefold()
        if found and "/job/" in "/" + path:
            return "workday", tenant, re.sub(r"[^a-z0-9]", "", found[1].casefold())
    if host == "jobs.smartrecruiters.com" and len(parts) == 2:
        found = re.match(r"(\d{8,})-", parts[1])
        if found:
            return "smartrecruiters", parts[0].casefold(), found[1]
    return None


def contextual_links(body: str, anchors: tuple[tuple[str, str, str], ...] = ()) -> tuple[str, ...]:
    """Only links explicitly presented as this application's posting.

    The caller supplies visible, unquoted HTML anchor text and preceding text.
    Recommended openings, accounts, tracking redirects and portal links never
    acquire identity just because they contain a number.
    """
    body = primary_link_text(body)
    claims = list(anchors)
    for match in re.finditer(r"https?://[^\s<>\"']+", body):
        claims.append((match[0].rstrip(".,;)"), "", body[max(0, match.start()-240):match.start()]))
    result = []
    for url, label, context in claims[:200]:
        primary = context[-240:] + " " + label
        if re.search(r"\b(?:unsubscribe|recommended|other (?:jobs|roles|opportunities)|you may also|similar (?:jobs|roles)|job alerts?)\b", primary, re.I):
            continue
        if not re.search(r"\b(?:your application|(?:you )?applied (?:for|to)|application for|(?:view|see) (?:the |your )?(?:job|position|application)(?: details)?|job details)\b", primary, re.I):
            continue
        if posting_identity(url) and url not in result:
            result.append(url)
    return tuple(result[:20])
