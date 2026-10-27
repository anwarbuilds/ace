"""Deterministic recruiting-email classification and matching.

This module has no Gmail access and no database writes. It decides what an
email says and which application it concerns.

Since 2026-10-26 the owner wants clear rejections recorded without a manual
step. A rejection is ``verified`` when its wording is explicit, Gmail
authenticated the sender, the sender is not a personal mailbox, the timing
fits and exactly one application fits: by job ID, by exact title at the named
company, or as the owner's only application at that company. Interviews,
assessments and offers keep the stricter rule: an exact job ID from the
employer's own domain. Receipts are filed without changing anything, and
everything uncertain goes to review with the likeliest application first.

Parser version 3 (2026-10-26) never files an email as a receipt when it also
sounds like a decision, or when only part of it could be read: a rejection
that opens with "thank you for applying" must reach the owner.

Parser version 4 (2026-10-26) reads the employer from a Workday sender:
Workday mails from <tenant>@myworkday.com, and the tenant names the employer
("generalmotors" is General Motors), so those emails can match by company.
Parser version 5 also accepts a tenant or domain made of the company's
initials ("cir" for Cambridge Investment Research).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from urllib.parse import urlparse

PARSER_VERSION = "6"

_OTHERS = r"(?:other|another|a\s+different|different|more\s+qualified|alternative)\s+(?:candidates?|applicants?|individuals?|profiles?)"
_ONWARD = r"(?:moving\s+(?:forward|ahead)|proceeding|progressing|advancing|continuing)"
_ELIGIBILITY_DECLINE = (
    r"(?:does\s+not\s+include\s+(?:visa\s+)?sponsorship|unable\s+to\s+sponsor"
    r"|not\s+eligible\s+for|does\s+not\s+meet\s+the\s+requirements"
    r"|decided\s+to\s+move\s+on|will\s+not\s+be\s+considering"
    r"|was\s+not\s+selected|not\s+able\s+to\s+offer)"
)
_REJECTION = re.compile(
    r"\b(?:"
    r"we\s+regret\s+to\s+(?:inform|let\s+you\s+know|advise|tell)|we\s+regret\s+that\s+(?:we|your)"
    r"|(?:mov(?:e|ed|ing)|go(?:ne|ing)?)\s+(?:forward|ahead)(?:\s+\w+){0,3}?\s+" + _OTHERS +
    r"|(?:proceed(?:ed|ing)?|pursu(?:e|ed|ing)|progress(?:ed|ing)?)(?:\s+\w+){0,3}?\s+" + _OTHERS +
    r"|(?:move\s+forward|proceed)\s+with\s+(?:a\s+)?candidates?\s+whose"
    r"|(?:decided|chosen|elected)\s+(?:not\s+to|to\s+not)\s+(?:move\s+forward|proceed|progress|continue|pursue|advance)"
    r"|(?:will|would|are|is)\s+not\s+be\s+" + _ONWARD +
    r"|won[’']t\s+be\s+(?:" + _ONWARD + r"|able\s+to\s+(?:move\s+forward|proceed|progress|offer\s+you))"
    r"|not\s+(?:be\s+)?able\s+to\s+(?:move\s+forward|proceed|progress|offer\s+you)"
    r"|not\s+(?:be\s+)?moving\s+forward\s+with\s+your\s+(?:application|candidacy)"
    r"|your\s+(?:application|candidacy)\s+(?:was|has\s+been|is)\s+(?:unsuccessful|declined|rejected|not\s+successful|not\s+selected)"
    r"|(?:have|has)\s+not\s+been\s+selected|you\s+were\s+not\s+selected"
    r"|(?:position|role|opening|requisition|job|posting)(?:\s+(?:that\s+)?you\s+applied\s+(?:for|to))?"
    r"\s+(?:has\s+been|was|is\s+now)\s+(?:filled|closed|cancell?ed)"
    r"|(?:position|role|opening|job)\s+is\s+no\s+longer\s+(?:available|open)"
    r"|(?:have|we['’]ve)\s+filled\s+(?:the|this)\s+(?:position|role|opening)"
    r"|unable\s+to\s+(?:offer\s+you|move\s+forward|proceed|progress)"
    r"|not\s+(?:be\s+)?extend(?:ing)?\s+(?:you\s+)?an\s+offer"
    r"|(?:decided|chosen)\s+to\s+go\s+(?:in\s+)?(?:a\s+)?different\s+direction"
    r"|no\s+longer\s+(?:considering|being\s+considered|under\s+consideration)"
    r"|" + _ELIGIBILITY_DECLINE + r")\b",
    re.I,
)
# Wording that sounds like a decision. An email that also thanks you for
# applying is shown to you rather than filed as a receipt.
_DECLINE = re.compile(
    r"\b(?:(?:won[’']t|will\s+not|not)\s+(?:be\s+)?" + _ONWARD +
    r"|regret|(?:other|another|more\s+qualified)\s+(?:candidates?|applicants?)|" + _ELIGIBILITY_DECLINE + r")\b",
    re.I,
)
# The owner withdrawing is not an employer rejection.
_WITHDRAWN = re.compile(
    r"\b(?:you(?:\s+have|['’]ve)?\s+(?:decided|chosen|elected)\s+(?:not\s+to|to\s+not|to\s+withdraw)"
    r"|you(?:\s+have|['’]ve)?\s+withdrawn|withdrawal\s+of\s+your\s+application)\b",
    re.I,
)
# Words that name a role, to tell a generic email from one about another job.
_ROLE = re.compile(r"\b(?:engineers?|developers?|scientists?|analysts?|interns?|internship|designers?|architects?|researchers?"
                   r"|programmers?|consultants?|specialists?|managers?)\b", re.I)
_FILLER = {"and", "the", "for", "with", "new", "grad", "graduate", "early", "career", "level", "entry", "remote", "hybrid",
           "onsite", "university", "college", "team"}
# A rejection phrase only counts in an email about an application.
_RECRUITING = re.compile(
    r"\b(?:applications?|applied|applying|candidacy|candidates?|positions?|roles?|opportunit(?:y|ies)"
    r"|requisitions?|req|jobs?|interviews?|recruit\w*|hiring)\b",
    re.I,
)
_ASSESSMENT = re.compile(
    r"\b(?:online\s+assessment|coding\s+(?:assessment|challenge|test)|technical\s+assessment"
    r"|take[\s-]home\s+(?:assessment|assignment|challenge)|hackerrank|codesignal|codility|hirevue|karat"
    r"|complete\s+(?:the|an|your)\s+assessment)\b",
    re.I,
)
_INTERVIEW = re.compile(
    r"\b(?:invite\s+you\s+to\s+(?:an?\s+)?interview|invitation\s+to\s+interview|interview\s+invitation"
    r"|schedule\s+(?:an?\s+|your\s+|a\s+time\s+for\s+(?:an?\s+)?)?(?:interview|phone\s+screen)"
    r"|next\s+round\s+of\s+interviews|move\s+(?:you\s+)?forward\s+to\s+the\s+next\s+(?:step|stage|round))\b",
    re.I,
)
_OFFER = re.compile(r"\b(?:offer\s+of\s+employment|pleased\s+to\s+offer\s+you|excited\s+to\s+offer\s+you|offer\s+letter)\b", re.I)
_CONFIRMATION = re.compile(
    r"\b(?:thank\s+you\s+for\s+(?:applying|your\s+application|submitting\s+your\s+application)|thanks\s+for\s+applying"
    r"|we(?:'ve|\s+have)\s+received\s+your\s+application|application\s+(?:has\s+been\s+)?(?:received|submitted)"
    r"|your\s+application\s+(?:has\s+been|was)\s+(?:received|submitted)|successfully\s+(?:applied|submitted))\b",
    re.I,
)
_RECRUITER = re.compile(
    r"\b(?:would\s+like\s+to\s+(?:speak|talk|connect)\s+with\s+you\s+about\s+(?:the|your)\s+(?:role|application)"
    r"|reaching\s+out\s+to\s+discuss\s+your\s+application)\b",
    re.I,
)
# A labelled job ID: "Ref: 137787", "Job ID R-1234", "Requisition #5521".
_REQ = re.compile(
    r"\b(?:requisition|req|job|posting|position|vacancy|reference|ref)\.?(?:\s*(?:id|number|no\.?|code))?"
    r"\s*[:#-]?\s*#?\s*([A-Za-z]{0,4}[-_]?\d[A-Za-z0-9._-]{2,40})",
    re.I,
)
# Unlabelled tokens with a digit, compared only with stored job IDs, and only
# for applications at a company the email names.
_ID_TOKEN = re.compile(r"\b[A-Za-z]{0,4}[-_]?\d[A-Za-z0-9_-]{3,40}\b")
_UNTRUSTED_DOMAIN = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com", "icloud.com",
                     "me.com", "aol.com", "proton.me", "protonmail.com"}
# Recruiting platforms send for many employers; their domain never names one.
_PLATFORM = ("greenhouse", "lever.co", "myworkday", "workday", "smartrecruiters", "ashbyhq", "icims", "jobvite", "taleo",
             "successfactors", "workable", "bamboohr", "jazzhr", "eightfold", "avature", "phenompeople", "oraclecloud",
             "brassring", "gem.com", "rippling", "teamtailor", "recruitee", "paylocity", "ultipro", "ukg", "adp.com",
             "applytojob", "breezy", "csod", "hirevue", "hackerrank", "codesignal", "linkedin")
# Shared by the conservative safety net and the SQL stale-mail selector.
RECRUITING_SENDERS = _PLATFORM
APPLICATION_WORDS = ("application", "applying", "applied", "candidacy", "candidate", "interest", "interview", "assessment")
JOB_WORDS = ("position", "role", "job", "engineer", "developer", "recruit", "hiring", "opportunity")
_JOB_BOARDS = {"linkedin.com", "indeed.com", "joinhandshake.com", "handshake.com", "glassdoor.com", "ziprecruiter.com"}
UNCLEAR_REASON = "Looks like it is about an application, but ACE could not tell what it says"


def is_job_board(sender: str) -> bool:
    domain = parseaddr(sender)[1].rpartition("@")[2].casefold()
    return any(domain == host or domain.endswith("." + host) for host in _JOB_BOARDS)


def application_related(evidence: EmailEvidence, applications: list[ApplicationIdentity]) -> bool:
    if is_job_board(evidence.sender):
        return False
    text = _words(f"{evidence.subject if not _forwarded(evidence.subject) else ''} {_new_text(evidence.body)}")
    if not any(re.search(r"\b" + word + r"\w*\b", text) for word in APPLICATION_WORDS):
        return False
    domain = parseaddr(evidence.sender)[1].rpartition("@")[2].casefold()
    display, labels = _sender_parts(evidence.sender)
    return (any(platform in domain for platform in RECRUITING_SENDERS)
            or any(re.search(r"\b" + word + r"\w*\b", text) for word in JOB_WORDS)
            or any(_named(_company_words(app.company), _words(f"{display} {text}"))
                   or _in_domain(_company_words(app.company), labels) for app in applications))


_LEGAL_SUFFIX = re.compile(r"\s+(?:inc|incorporated|llc|ltd|limited|corp|corporation|co|company|plc|gmbh|lp|llp)$")
# An email received slightly before the owner marked Applied in ACE is
# still about that application: some employers reject within minutes.
_MARKING_GRACE = timedelta(hours=24)
# Receipts ACE filed itself; a later parser may read them again. Receipts the
# owner filed carry their own reason and are never re-decided.
RECEIPT_REASON = "Application receipt; no status change"
PARTIAL_REASON = "Only part of this email could be read"


@dataclass(frozen=True)
class ApplicationIdentity:
    key: str
    company: str
    title: str
    requisition_id: str | None
    submitted_at: datetime | None
    current_status: str
    official_url: str | None = None
    status_changed_at: datetime | None = None


@dataclass(frozen=True)
class EmailEvidence:
    sender: str
    subject: str
    body: str
    received_at: datetime
    sender_authenticated: bool = False
    # False when only Gmail's short snippet could be read, not the body.
    complete: bool = True


@dataclass(frozen=True)
class Decision:
    classification: str
    requisition_id: str | None
    candidates: tuple[str, ...]
    target: str | None
    disposition: str
    reason: str
    sender_verified: bool


def _new_text(body: str) -> str:
    """Drop common quoted/forwarded material before looking for intent."""
    return re.split(r"(?im)^\s*(?:on .{5,160} wrote:|[- ]*forwarded message[- ]*|from:\s.+$|>.*$)", body, maxsplit=1)[0][:8000]


def _forwarded(subject: str) -> bool:
    return bool(re.match(r"(?i)^\s*(?:fwd?|forward):", subject))


def _labelled_ids(text: str) -> set[str]:
    found = set()
    for match in _REQ.finditer(text):
        token = match.group(1).rstrip("._-").casefold()
        # A year or a short number is not a job ID.
        if re.fullmatch(r"(?:19|20)\d{2}", token) or sum(c.isdigit() for c in token) < 3:
            continue
        found.add(token)
    return found


def classify(evidence: EmailEvidence) -> tuple[str, str | None]:
    subject = "" if _forwarded(evidence.subject) else evidence.subject
    text = f"{subject}\n{_new_text(evidence.body)}"
    reqs = _labelled_ids(text)
    requisition = next(iter(reqs)) if len(reqs) == 1 else None
    # A conditional instruction ("if you are not eligible ...") does not
    # establish that the employer has rejected this particular application.
    asserted = any(not re.search(r"\b(?:if|unless|whether|in\s+case|does\s+not\s+mean)\b[^.!?\n]{0,160}$",
                                 text[max(0, match.start()-180):match.start()], re.I)
                   for match in _REJECTION.finditer(text))
    if asserted and _RECRUITING.search(text) and not _WITHDRAWN.search(text):
        return "rejection", requisition
    if _OFFER.search(text):
        return "offer", requisition
    if _INTERVIEW.search(text):
        return "interview", requisition
    if _ASSESSMENT.search(text):
        return "online_assessment", requisition
    if _RECRUITER.search(text):
        return "recruiter_reply", requisition
    if _CONFIRMATION.search(text):
        return ("possible_rejection" if _DECLINE.search(text) else "application_confirmation"), requisition
    return "unknown", requisition


def _words(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _company_words(company: str) -> str:
    return re.sub(r"^the\s+", "", _LEGAL_SUFFIX.sub("", _words(company)))


def _id_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _aware(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def _sender_matches(sender: str, app: ApplicationIdentity) -> bool:
    """Only an exact employer host or its subdomain establishes origin.

    Shared ATS domains and personal email hosts never establish employer
    identity. Required for automatic interviews, assessments and offers.
    """
    host = (urlparse(app.official_url or "").hostname or "").lower()
    domain = parseaddr(sender)[1].rpartition("@")[2].lower()
    if not host or not domain or domain in _UNTRUSTED_DOMAIN:
        return False
    if any(x in host for x in ("greenhouse.io", "lever.co", "myworkdayjobs.com", "ashbyhq.com")):
        return False
    return domain == host or domain.endswith("." + host)


def _sender_trusted(evidence: EmailEvidence) -> bool:
    """Gmail authenticated the visible sender, and it is not a personal mailbox."""
    domain = parseaddr(evidence.sender)[1].rpartition("@")[2].lower()
    return evidence.sender_authenticated and bool(domain) and domain not in _UNTRUSTED_DOMAIN


def _sender_parts(sender: str) -> tuple[str, list[str]]:
    """The display name, and the labels of a domain that can name an employer."""
    name, address = parseaddr(sender)
    local, _, domain = address.casefold().rpartition("@")
    if domain == "myworkday.com" or domain.endswith(".myworkday.com"):
        # Workday sends as the employer's tenant: generalmotors@myworkday.com.
        tenant = re.sub(r"\d+$", "", local)
        return name, [tenant] if re.fullmatch(r"[a-z][a-z0-9]{2,}", tenant) else []
    if not domain or domain in _UNTRUSTED_DOMAIN or any(platform in domain for platform in _PLATFORM):
        return name, []
    return name, [label for label in domain.split(".")[:-1] if len(label) >= 2]


def _named(words: str, haystack: str) -> bool:
    return len(words) >= 2 and f" {words} " in f" {haystack} "


def _in_domain(name: str, labels: list[str]) -> bool:
    first = name.split()[0] if name else ""
    # A tenant or domain can also be the initials: cir is Cambridge Investment Research.
    initials = "".join(word[0] for word in name.split())
    return bool(name) and (name.replace(" ", "") in labels or (len(first) >= 5 and first in labels)
                           or (len(initials) >= 3 and initials in labels))


def _title_overlap(title: str, words: set[str]) -> float:
    """The share of a job title's distinctive words that the email uses."""
    core = {word for word in _words(title).split() if len(word) >= 3 and not word.isdigit() and word not in _FILLER}
    return len(core & words) / len(core) if core else 0.0


@dataclass(frozen=True)
class _Match:
    target: str | None
    basis: str  # How the target was found, or why none was.
    ranked: tuple[str, ...]
    requisition: str | None


def _match(evidence: EmailEvidence, applications: list[ApplicationIdentity], labelled: str | None) -> _Match:
    subject = "" if _forwarded(evidence.subject) else evidence.subject
    body = _new_text(evidence.body)
    display, labels = _sender_parts(evidence.sender)
    strong_text = _words(f"{display} {subject}")
    all_text = _words(f"{display} {subject} {body}")
    by_company: dict[str, list[ApplicationIdentity]] = {}
    for app in applications:
        by_company.setdefault(_company_words(app.company), []).append(app)
    # Named in the sender or subject is strong; only in the body is weak.
    strong = {name for name in by_company if _named(name, strong_text) or _in_domain(name, labels)}
    weak = {name for name in by_company if name not in strong and _named(name, all_text)}

    labelled_key = _id_key(labelled) if labelled else None
    ids = {_id_key(token) for token in _ID_TOKEN.findall(f"{subject} {body}") if not re.fullmatch(r"(?:19|20)\d{2}", token)}
    ids |= {labelled_key} if labelled_key else set()
    words = set(all_text.split())
    by_id = [app for app in applications if app.requisition_id and len(_id_key(app.requisition_id)) >= 4
             and _id_key(app.requisition_id) in ids
             and (_id_key(app.requisition_id) == labelled_key or _company_words(app.company) in strong | weak)]

    def score(app: ApplicationIdentity) -> int:
        name = _company_words(app.company)
        title = _words(app.title)
        value = 100 if app in by_id else 0
        value += 40 if name in strong else 20 if name in weak else 0
        if _named(title, all_text):
            value += 30
        else:
            value += round(20 * _title_overlap(app.title, words))
        return value

    considered = [app for app in applications if app in by_id or _company_words(app.company) in strong | weak]
    ranked = sorted(considered, key=lambda app: (-score(app), -_aware(app.submitted_at).timestamp() if app.submitted_at else 0, app.key))
    keys = tuple(app.key for app in ranked[:10])
    if len(by_id) == 1:
        return _Match(by_id[0].key, "its job ID", keys, by_id[0].requisition_id)
    if len(by_id) > 1:
        return _Match(None, "More than one application has this job ID", tuple(app.key for app in by_id), labelled)
    named = strong or weak
    if not named:
        return _Match(None, "No application could be matched with confidence", keys, labelled)
    if len(named) > 1:
        return _Match(None, "The email names more than one company you applied to", keys, labelled)
    company_apps = by_company[next(iter(named))]

    def other_job(app: ApplicationIdentity) -> bool:
        # The email names a job ID, and it is not this application's.
        return bool(labelled_key and app.requisition_id and _id_key(app.requisition_id) != labelled_key)

    titled = [app for app in company_apps if _named(_words(app.title), all_text)]
    if len(titled) == 1 and not other_job(titled[0]):
        return _Match(titled[0].key, "its exact title", keys, labelled)
    # The only application at the company, unless the email is about a
    # role with a different title.
    only = company_apps[0]
    if strong and len(company_apps) == 1 and not titled and not other_job(only) \
            and (_title_overlap(only.title, words) >= 0.5 or not _ROLE.search(f"{subject} {body}")):
        return _Match(only.key, "your only application there", keys, labelled)
    if len(company_apps) > 1:
        return _Match(None, "You applied to several roles there and the email does not say which", keys, labelled)
    if not strong:
        return _Match(None, "The company is named only in the email text", keys, labelled)
    return _Match(None, "The email may be about a different role there", keys, labelled)


def reconcile(evidence: EmailEvidence, applications: list[ApplicationIdentity], account: str | None = None) -> Decision:
    if account and parseaddr(evidence.sender)[1].casefold() == account.casefold():
        return Decision("unknown", None, (), None, "ignored", "Sent by the connected account", False)
    classification, req = classify(evidence)
    if classification == "unknown" and not application_related(evidence, applications):
        return Decision(classification, req, (), None, "ignored", "No explicit recruiting outcome", False)
    found = _match(evidence, applications, req)
    if classification == "unknown":
        return Decision("unclear", found.requisition, found.ranked, None, "review", UNCLEAR_REASON, False)
    if classification == "application_confirmation":
        if not evidence.complete:
            return Decision(classification, found.requisition, found.ranked, None, "review", PARTIAL_REASON, False)
        return Decision(classification, found.requisition, found.ranked, found.target, "receipt", RECEIPT_REASON, False)
    if classification == "possible_rejection":
        return Decision(classification, found.requisition, found.ranked, None, "review",
                        "It may be a rejection, but the wording is not clear enough to record on its own", False)
    if found.target is None:
        return Decision(classification, found.requisition, found.ranked, None, "review", found.basis, False)
    app = next(a for a in applications if a.key == found.target)
    candidates = (app.key,) + tuple(key for key in found.ranked if key != app.key)
    if classification == "rejection":
        if not _sender_trusted(evidence):
            return Decision(classification, found.requisition, candidates, None, "review", "Sender could not be authenticated", False)
    elif not (evidence.sender_authenticated and found.basis == "its job ID" and _sender_matches(evidence.sender, app)):
        return Decision(classification, found.requisition, candidates, None, "review",
                        "Matched by " + found.basis + "; positive outcomes need your confirmation", False)
    reason = conflict(app, classification, evidence.received_at)
    if reason:
        return Decision(classification, found.requisition, candidates, None, "review", reason, True)
    return Decision(classification, found.requisition, candidates, app.key, "verified",
                    "Clear " + classification.replace("_", " ") + " matched by " + found.basis, True)


def conflict(app: ApplicationIdentity, classification: str, received_at: datetime) -> str | None:
    """Why this outcome must not change the application, if it must not.

    The caller checks again against the live record just before writing.
    """
    received = _aware(received_at)
    if app.submitted_at is not None and _aware(app.submitted_at) - _MARKING_GRACE > received:
        return "Email predates application"
    if classification == "rejection" and app.current_status == "rejected":
        return None  # Already rejected: the email only adds its date.
    if app.current_status in {"accepted", "withdrawn"} or (classification == "rejection" and app.current_status == "offer") \
            or (classification != "rejection" and app.current_status == "rejected"):
        return "Existing final status is protected"
    # Marking Applied also stamps the change time, and the grace above
    # already covers it; only a later stage is protected here.
    if app.current_status != "applied" and app.status_changed_at is not None and _aware(app.status_changed_at) > received:
        return "Newer application status is protected"
    return None
