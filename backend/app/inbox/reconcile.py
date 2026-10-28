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
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from urllib.parse import urlparse

PARSER_VERSION = "9"
MAX_CLASSIFIER_BODY = 60000

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
    r"|(?:will\s+not|cannot|can[’']t)\s+(?:move\s+forward|proceed|progress|continue|advance)\s+with\s+your\s+(?:application|candidacy)" +
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
    r"|take[\s-]home\s+(?:assessment|assignment|challenge)"
    r"|(?:invited|invite you|invitation)\s+(?:to\s+)?(?:a\s+)?(?:hackerrank|codesignal|codility|hirevue|karat)"
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
    r"|we(?:'ve|\s+have)?\s+received\s+your\s+application|application\s+(?:has\s+been\s+)?(?:received|submitted)"
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
    matched_target: str | None = None


def _new_text(body: str) -> str:
    """Drop common quoted/forwarded material before looking for intent."""
    return re.split(r"(?im)^\s*(?:on .{5,160} wrote:|[- ]*(?:forwarded|original) message[- ]*|from:\s.+$|>.*$|--\s*$|unsubscribe\b|manage (?:your )?(?:email preferences|job alerts)\b)", body, maxsplit=1)[0][:MAX_CLASSIFIER_BODY]


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


def routine_notification(evidence: EmailEvidence) -> bool:
    """Primary account/job-alert subjects do not establish an application outcome.

    Do not search footers for these words: a real interview can contain links
    to account settings or job alerts without becoming a notification.
    """
    subject = evidence.subject.casefold()
    if _REJECTION.search(subject) or _INTERVIEW.search(subject) or _OFFER.search(subject):
        return False
    primary = _new_text(evidence.body)[:1200]
    subject_notice = bool(re.search(
        r"\b(?:verify your (?:email|account)|(?:email|account) verification|verification code"
        r"|reset (?:your )?password|password reset|sign[ -]?in code|one[ -]time (?:code|password)"
        r"|job alerts?|job recommendations?|recommended jobs?|jobs? for you|new jobs? (?:for|matching)"
        r"|job digest|jobs? you might|weekly (?:jobs?|career) digest)\b", subject))
    account_action = re.search(
        r"\b(?:(?:verify|verification|confirm) (?:your )?(?:email|account)|(?:reset|change) (?:your )?password"
        r"|(?:verification|sign[ -]?in|one[ -]?time) code|(?:your )?account (?:is (?:ready|active)|has been (?:created|activated)))\b", primary, re.I)
    recommendations = re.search(r"\b(?:recommended jobs|new jobs for you|job recommendations|jobs matching your)\b", primary, re.I)
    practice = re.search(r"\b(?:your practice (?:score|results?)|practice (?:assessment|test) (?:results?|score))\b", primary, re.I)
    return bool((subject_notice and (account_action or recommendations)) or practice)



# The public catalog documents contextual requirements for these patterns.
# A Reading describes communication intent. Matching and policy run afterwards.
@dataclass(frozen=True)
class Reading:
    classification: str
    requisition_id: str | None
    explanation: str
    excerpt: str
    variant: str = ""


CLASSIFICATION_REASONS = {
    "rejection": "The employer communicates a definite decision to end this candidacy.",
    "application_confirmation": "The employer confirms receipt or continued review, without a hiring outcome.",
    "online_assessment": "The employer requests a hiring assessment or reminds the candidate to complete it.",
    "assessment_completed": "The message confirms an assessment was completed; it does not invite another test.",
    "assessment_cancelled": "The assessment was cancelled; this alone does not reject the application.",
    "interview": "The employer invites, schedules or reschedules an interview or recruiter screen.",
    "interview_cancelled": "An interview was cancelled; this alone does not end the candidacy.",
    "recruiter_reply": "The recruiter discusses the application beyond a submission receipt.",
    "offer": "The employer explicitly offers employment or sends an actual employment offer letter.",
    "action_required": "The employer requests candidate information, documents or another application action.",
    "status_update": "The message describes application progress without a confirmed hiring outcome.",
    "possible_rejection": "Decision statements conflict or leave the actual outcome unresolved.",
    "unclear": "Application correspondence is retained; no confirmed outcome has been established.",
    "unknown": "No applicant-specific hiring outcome has been established.",
}
PASSIVE_KINDS = {"assessment_completed", "assessment_cancelled", "interview_cancelled", "status_update"}


def _asserted(pattern, text: str):
    """Return asserted spans, excluding conditions, reported examples and negation.

    Sentence context is deliberately kept: moving past a semicolon must not
    turn an eligibility condition or process description into an actual decision.
    """
    for match in pattern.finditer(text):
        start = max(text.rfind(c, 0, match.start()) for c in ".!?\n") + 1
        end = min((pos for c in ".!?\n" if (pos := text.find(c, match.end())) >= 0), default=len(text))
        sentence = text[start:end]
        prefix = text[start:match.start()]
        if re.search(r"\b(?:if|unless|whether|until|in case|does not mean|doesn't mean|for example|such as)\b", sentence, re.I):
            continue
        if re.search(r"\b(?:not|never|no longer)\s+(?:(?:been|being|actually|an?|the)\s+)?$", prefix, re.I):
            continue
        if re.search(r"\b(?:not selected|not been selected)\b[^.!?\n]{0,40}\byet\b", sentence, re.I):
            continue
        if re.search(r"[\"“]\s*$", prefix) or re.search(r"\b(?:might|may|could|would)\s+(?:be\s+)?$", prefix, re.I):
            continue
        yield match, text[start:end].strip()


def _reading(kind: str, req: str | None, excerpt: str, variant: str = "") -> Reading:
    return Reading(kind, req, CLASSIFICATION_REASONS[kind], re.sub(r"\s+", " ", excerpt).strip()[:500], variant)


# Specific candidate-ending statements, rather than regret or policy by itself.
_ENDING = re.compile(
    r"\b(?:your (?:application|candidacy) (?:was|is|has been) (?:not selected|unsuccessful|declined|rejected|not successful)"
    r"|you (?:were|have) not (?:been )?selected"
    r"|(?:will not|won['’]t|cannot|can['’]t|unable to|not able to|decided not to|decided to not) "
    r"(?:be )?(?:mov(?:e|ing) (?:forward|ahead)|proceed(?:ing)?|advanc(?:e|ing)|continu(?:e|ing)|progress(?:ing)?)"
    r"|(?:are|is) not (?:be )?(?:moving (?:forward|ahead)|proceeding|advancing|continuing)"
    r"|(?:chosen|decided|elected) (?:not to|to not) (?:pursue|continue|advance|proceed)"
    r"|(?:chosen|decided) to go (?:in )?(?:a )?different direction"
    r"|(?:chose|chosen) another path"
    r"|(?:will not|not be|won['’]t be|not|unable to|cannot|not able to) (?:able to )?(?:extend(?:ing)? (?:you )?an offer|offer(?:ing)? you|offer a position)"
    r"|no longer (?:considering you|being considered|under consideration)"
    r"|(?:you are|your application is) not eligible for (?:this|the) (?:position|role|job)"
    r"|your application does not meet (?:the|our) requirements"
    r"|will not be considering (?:you|your application))\b", re.I)
_OTHER_DECISION = re.compile(
    r"\b(?:(?:have |has |we['’]ve )?(?:decided|chosen|elected) to "
    r"(?:move (?:forward|ahead)|pursue|proceed|progress|go)(?:\s+\w+){0,3}\s+" + _OTHERS +
    r"|(?:have |has |we['’]ve )(?:selected|chosen) " + _OTHERS +
    r"|(?:moving (?:forward|ahead)|pursuing|proceeding)(?:\s+\w+){0,3}\s+" + _OTHERS + r")\b", re.I)
_ASSESSMENT_NOUN = r"(?:(?:(?:online|technical|pre-employment|hiring|coding) )?assessment|coding (?:challenge|test)|technical (?:evaluation|test)|screening test|work simulation|take[ -]home (?:assignment|challenge)|(?:HackerRank|CodeSignal|Codility|HireVue) (?:test|challenge))"
_INTERVIEW_NOUN = r"(?:(?:technical |phone |video |onsite |hiring.manager |recruiter )?interview|(?:phone|recruiter) screen(?:ing)?|screening (?:call|conversation))"


def read_intent(evidence: EmailEvidence) -> Reading:
    body = re.sub(r"(?<!\n)\n(?!\n)", " ", _new_text(evidence.body).replace("\r\n", "\n"))
    subject = "" if _forwarded(evidence.subject) else evidence.subject
    reqs = _labelled_ids(subject + "\n" + body)
    req = next(iter(reqs)) if len(reqs) == 1 else None
    # Only current substantive content establishes intent. Subjects can supply
    # identity, but an outcome in a subject cannot defeat an unrelated body.
    recruiting = bool(_RECRUITING.search(subject + "\n" + body))
    if re.search(r"\b(?:loan|mortgage|credit card|passport|bank account)\b", body, re.I) and not _ROLE.search(body):
        return _reading("unknown", req, "")
    negative = list(_asserted(_ENDING, body)) + list(_asserted(_OTHER_DECISION, body))
    for span in _asserted(_REJECTION, body):
        wording = span[0].group().casefold()
        if (re.match(r"we\s+regret", wording) or re.search(r"sponsor|not eligible for|requirements|decided to move on", wording)
                or re.search(r"(?:position|role|opening|requisition|job|posting).*(?:filled|closed|cancel|available|open)", wording)):
            continue
        negative.append(span)
    negative = [span for span in negative if not (
        re.search(r"interview|assessment", span[1], re.I) and re.search(r"scheduled time|technical difficulties|reschedul|scheduling", span[1], re.I)
        and not re.search(r"your application|your candidacy", span[1], re.I))]
    # Closure is applicant-ending only when specifically tied to this application.
    closure = re.compile(r"\b(?:position|role|opening)(?: that)? you applied (?:for|to) (?:has been|was|is now) (?:filled|closed|cancelled)\b", re.I)
    negative += list(_asserted(closure, body))
    # A receipt about a particular application can explain closure of that role.
    if _CONFIRMATION.search(body):
        negative += list(_asserted(re.compile(r"\bthe (?:position|role) is no longer (?:available|open)\b", re.I), body))
    if _CONFIRMATION.search(body):
        negative += list(_asserted(re.compile(r"\bit has been (?:filled|closed|cancelled)\b", re.I), body))
    # Sponsorship policy alone is information. An explicit personal eligibility
    # decision or refusal to continue is captured by _ENDING instead.
    offer = list(_asserted(re.compile(
        r"\b(?:(?:pleased|excited|delighted) to offer you (?:the |a |an )?(?:(?-i:[A-Z][\w-]+(?: [A-Z][\w-]+){0,7}) )?(?:position|role|job|employment)"
        r"|(?:attached|enclosed|please (?:review|sign|accept)) (?:employment )?offer letter"
        r"|(?:extend|extending) (?:you )?an offer of employment)\b", re.I), body))
    # A completed test can be followed by a new interview request. That new
    # requested action is the primary intent, rather than the earlier completion.
    interview_request = list(_asserted(re.compile(
        r"\b(?:invite you to|invited to|please schedule|please reschedule) (?:a |an |your |the )?(?:technical |phone |video |recruiter )?(?:interview|screen)\b", re.I), body))
    if interview_request and not negative and re.search(_ASSESSMENT_NOUN, body, re.I) and re.search(r"\b(?:completed|submitted|finished)\b", body, re.I):
        return _reading("interview", req, interview_request[0][1], "invitation")
    still_review = re.search(r"\byour application (?:is|remains) (?:still )?under (?:review|consideration)\b", body, re.I)
    if negative and still_review and still_review.start() > min(span[0].start() for span in negative):
        return _reading("possible_rejection", req, negative[0][1] + " " + still_review.group(), "conflicting_progress")
    if negative and interview_request:
        return _reading("possible_rejection", req, negative[0][1] + " " + interview_request[0][1], "conflicting_outcomes")
    if negative and offer:
        return _reading("possible_rejection", req, negative[0][1] + " " + offer[0][1], "conflicting_outcomes")
    if negative and recruiting and not _WITHDRAWN.search(body):
        # A correction explicitly rescinding a rejection needs owner attention.
        if re.search(r"\b(?:in error|incorrect|mistaken|disregard|not (?:been )?rejected)\b", body, re.I):
            return _reading("possible_rejection", req, negative[0][1], "corrected_decision")
        return _reading("rejection", req, negative[0][1])
    if offer:
        return _reading("offer", req, offer[0][1], "employment_offer")

    for noun, kind in ((_ASSESSMENT_NOUN, "assessment"), (_INTERVIEW_NOUN, "interview")):
        # Completion/cancellation takes precedence over the original invitation
        # often repeated in the same message. Neither creates a new outcome.
        for state, words in (("cancelled", r"cancelled|canceled|cancellation"), ("completed", r"completed|submitted|finished|completion")):
            if kind == "interview" and state == "completed":
                continue
            pattern = re.compile(r"\b(?:" + noun + r")[^.!?\n]{0,65}\b(?:" + words + r")\b|\b(?:" + words + r")[^.!?\n]{0,65}\b(?:" + noun + r")\b", re.I)
            spans = list(_asserted(pattern, body))
            if spans and not re.search(r"\b(?:not|not yet|once|when|after you have)\b[^.!?\n]{0,50}(?:" + words + r")\b", spans[0][1], re.I):
                return _reading(kind + "_" + state, req, spans[0][1], state)
        action = re.compile(
            r"\b(?:invite you to|invited to|invitation to|please (?:complete|take|schedule|book)|complete (?:the|an|your)|take (?:the|an|your)|schedule (?:an?|your|a time for an?)|availability for|selected for|reminder[^.!?\n]{0,35}(?:complete|take)|reschedule (?:your|the))\s+(?:a |an |the |your )?(?:" + noun + r")\b"
            r"|\b(?:" + noun + r")[^.!?\n]{0,60}\b(?:invitation|invite|scheduled|confirmed|rescheduled|deadline|due by|due on|reminder|please complete)\b", re.I)
        spans = list(_asserted(action, body))
        if spans:
            sentence = spans[0][1]
            if re.search(r"\b(?:practice|webinar|demo|sample|course)\b", sentence, re.I):
                continue
            variant = "rescheduled" if re.search(r"reschedul", sentence, re.I) else "reminder" if re.search(r"reminder|deadline|due (?:by|on)", sentence, re.I) else "scheduled" if re.search(r"scheduled|confirmed", sentence, re.I) else "invitation"
            return _reading("online_assessment" if kind == "assessment" else "interview", req, sentence, variant)

    response = list(_asserted(_RECRUITER, body))
    if response:
        return _reading("recruiter_reply", req, response[0][1])
    action = list(_asserted(re.compile(
        r"\b(?:please|could you|we (?:need|request)|you (?:must|need to)) (?:provide|send|upload|submit|confirm|update|complete) "
        r"(?:us with |a |an |the |your |additional |following )*(?:documents?|transcripts?|resume|information|availability|candidate profile|application form|work authorization|portfolio)\b", re.I), body))
    if action and recruiting:
        return _reading("action_required", req, action[0][1])
    receipt = list(_asserted(_CONFIRMATION, body))
    progress = list(_asserted(re.compile(
        r"\b(?:your application (?:is|remains|has been selected for) (?:still )?(?:under|in|further) (?:review|consideration)"
        r"|we (?:are |will be )?(?:still )?reviewing your (?:application|qualifications|details)"
        r"|application (?:is|remains) under consideration)\b", re.I), body))
    if receipt or progress:
        # Other candidates being reviewed, regret about delays and policy
        # disclaimers describe process, not a negative decision.
        unresolved = list(_asserted(re.compile(r"\b(?:decision|outcome|results?)\b[^.!?\n]{0,80}\b(?:regret|other candidates)\b", re.I), body))
        if unresolved:
            return _reading("possible_rejection", req, unresolved[0][1])
        return _reading("application_confirmation", req, (receipt or progress)[0][1], "under_review" if progress else "receipt")
    if recruiting and re.search(r"\b(?:position|role|posting|requisition) (?:has been|is|was) (?:filled|closed|cancelled)|still (?:reviewing|considering)|next (?:step|stage|round)|sponsorship|immigration policy\b", body, re.I):
        return _reading("status_update", req, body[:500])
    uncertain = list(_asserted(_DECLINE, body))
    if uncertain and recruiting and re.search(r"\b(?:decision|outcome|results?)\b", body, re.I) and not _WITHDRAWN.search(body):
        return _reading("possible_rejection", req, uncertain[0][1])
    return _reading("unknown", req, "")


def classify(evidence: EmailEvidence) -> tuple[str, str | None]:
    reading = read_intent(evidence)
    return reading.classification, reading.requisition_id


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
    if len(_labelled_ids(f"{subject} {body}")) > 1:
        return _Match(None, "The email names multiple requisitions; choose the application it concerns", keys, labelled)
    if len(by_id) == 1 and len(strong) > 1:
        return _Match(None, "The email names more than one company you applied to", keys, labelled)
    if len(by_id) == 1 and strong and _company_words(by_id[0].company) not in strong:
        return _Match(None, "The requisition and named employer point to different applications", keys, labelled)
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


def reconcile(evidence: EmailEvidence, applications: list[ApplicationIdentity], account: str | None = None, *, thread_keys: tuple[str, ...] = ()) -> Decision:
    found = None
    def decided(*args):
        return Decision(*args, matched_target=found.target if found and evidence.complete else None)
    if account and parseaddr(evidence.sender)[1].casefold() == account.casefold():
        return decided("unknown", None, (), None, "ignored", "Sent by the connected account", False)
    classification, req = classify(evidence)
    # A generic account subject cannot suppress an explicit outcome in the body.
    if classification in {"unknown", "application_confirmation"} and evidence.complete and routine_notification(evidence):
        return decided("unknown", None, (), None, "ignored", "Routine account notification or job alert", False)
    if classification == "unknown" and not application_related(evidence, applications):
        return decided(classification, req, (), None, "ignored", "No explicit recruiting outcome", False)
    found = _match(evidence, applications, req)
    if classification == "unknown" and not evidence.complete:
        return decided("unclear", found.requisition, found.ranked, None, "review", PARTIAL_REASON, False)
    if classification == "unknown":
        return decided("unclear", found.requisition, found.ranked, None, "update", "Saved application correspondence; no confirmed outcome to record", False)
    # A single retained, previously matched message in this Gmail thread can
    # disambiguate roles at the same company. It cannot override a named ID,
    # company conflict, different role, positive policy or timing/status guards.
    if (classification == "rejection" and found.target is None and len(set(thread_keys)) == 1
            and found.basis == "You applied to several roles there and the email does not say which"
            and thread_keys[0] in found.ranked):
        linked = [app for app in applications if app.key == thread_keys[0]]
        narrowed = _match(evidence, linked, req)
        if narrowed.target:
            found = _Match(narrowed.target, "a previously linked message in this thread", found.ranked, narrowed.requisition)
    # A clipped body or snippet cannot establish that a later sentence names
    # another role or changes the apparent outcome. Preserve it for review.
    if not evidence.complete:
        return decided(classification, found.requisition, found.ranked, None, "review", PARTIAL_REASON, False)
    if classification in PASSIVE_KINDS:
        return decided(classification, found.requisition, found.ranked, found.target, "update",
                        CLASSIFICATION_REASONS[classification], False)
    if classification == "action_required":
        return decided(classification, found.requisition, found.ranked, found.target, "review",
                        "The employer requests documents or candidate information; complete that action on the employer site", False)
    if classification == "application_confirmation":
        return decided(classification, found.requisition, found.ranked, found.target, "receipt", RECEIPT_REASON, False)
    if classification == "possible_rejection":
        return decided(classification, found.requisition, found.ranked, None, "review",
                        "It may be a rejection, but the wording is not clear enough to record on its own", False)
    if found.target is None:
        return decided(classification, found.requisition, found.ranked, None, "review", found.basis, False)
    app = next(a for a in applications if a.key == found.target)
    candidates = (app.key,) + tuple(key for key in found.ranked if key != app.key)
    if classification == "rejection":
        if not _sender_trusted(evidence):
            return decided(classification, found.requisition, candidates, None, "review", "Sender could not be authenticated", False)
    elif not (evidence.sender_authenticated and found.basis == "its job ID" and _sender_matches(evidence.sender, app)):
        return decided(classification, found.requisition, candidates, None, "review",
                        "Matched by " + found.basis + "; positive outcomes need your confirmation", False)
    reason = conflict(app, classification, evidence.received_at)
    if reason:
        return decided(classification, found.requisition, candidates, None, "review", reason, True)
    return decided(classification, found.requisition, candidates, app.key, "verified",
                    "Clear " + classification.replace("_", " ") + " matched by " + found.basis, True)



PREVIOUS_OUTCOME_UNRESOLVED = "An earlier reading found {kind}; the current body does not establish that outcome. Confirm the employer's actual decision"


def reassess(evidence: EmailEvidence, applications: list[ApplicationIdentity], previous_classification: str,
             account: str | None = None, *, thread_keys: tuple[str, ...] = (), previous_reason: str = "") -> Decision:
    decision = reconcile(evidence, applications, account, thread_keys=thread_keys)
    prior_uncertainty = previous_reason.startswith("An earlier reading found ")
    if ((previous_classification in {"rejection", "possible_rejection", "offer", "interview", "online_assessment", "recruiter_reply"} or prior_uncertainty)
            and decision.classification in {"unknown", "unclear"} and decision.disposition in {"ignored", "update"}
            and evidence.complete and decision.reason != "Sent by the connected account" and not routine_notification(evidence)):
        # A real change in interpretation is material uncertainty. Retain it in
        # review instead of treating unknown wording as proof of routine intent.
        return replace(decision, classification="unclear", disposition="review", target=None,
                       reason=previous_reason if prior_uncertainty else PREVIOUS_OUTCOME_UNRESOLVED.format(kind=previous_classification.replace("_", " ")))
    return decision

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
    stages = {"applied": 0, "screening": 1, "interviewing": 2, "offer": 3, "accepted": 4}
    positive_stage = {"online_assessment": 1, "recruiter_reply": 1, "interview": 2, "offer": 3}.get(classification)
    if positive_stage is not None and stages.get(app.current_status, 0) > positive_stage:
        return "Existing later application stage is protected"
    # Marking Applied also stamps the change time, and the grace above
    # already covers it; only a later stage is protected here.
    if app.current_status != "applied" and app.status_changed_at is not None and _aware(app.status_changed_at) > received:
        return "Newer application status is protected"
    return None
