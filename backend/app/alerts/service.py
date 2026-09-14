"""One email per pull, once the pull is finished.

ACE deleted its entire email subsystem on 2026-09-06 -- outbox,
digests, SMTP, delivery worker, roughly 4,000 lines -- because the web
application was the only surface being watched. This is not that system
returning. The reason changed: alerts exist now so an application can be
started from a phone, away from the laptop, which a web page you have to
be sitting in front of cannot do.

So it stays deliberately small. No outbox, no delivery worker, no retry
schedule. One HTTPS call when a pull finishes, and a timestamp saying it
happened.

Why a pull is the unit
----------------------

A pull is a fifteen-minute bucket in ``poll_sessions``: every quarter
hour with any activity is exactly one row. That is already how the
interface groups arrivals, and it is what a person means by "this
morning's pull".

Alerting per job would send twenty emails on an ordinary day and, on the
two days new sources were registered, 140 and 185. Alerting per
scheduler cycle would be worse: a cycle runs every few seconds.

A bucket is only alerted once it has closed, because a bucket still
being written to is a pull still arriving, and half a pull is not worth
an email.
"""

from __future__ import annotations

import logging
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.intelligence.companies import (
    CompanyTier,
    classify_company,
)
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    JobResumeScoreRecord,
    PollSessionRecord,
    ResumeRecord,
)
from backend.app.mail.sender import send as send_mail
from backend.app.persistence.sessions import (
    SESSION_BUCKET,
    _as_utc,
)


LOGGER = logging.getLogger(
    "ace.alerts",
)


# Listed in full up to this many; beyond it the email says how many
# more rather than running to several screens on a phone. The two
# source-expansion days produced 140 and 185 qualifying jobs in a day,
# and a single pull on such a day can hold dozens.
MAX_LISTED = 25


# A pull older than this is not worth an email. Protects against a
# scheduler that was stopped for a week coming back and mailing every
# quarter hour it missed.
MAX_AGE = timedelta(
    hours=12,
)


def pending_pulls(
    session: Session,
    *,
    now: datetime | None = None,
) -> list[PollSessionRecord]:
    """Closed pulls that found something and have not been alerted.

    Ordered oldest first, so a backlog arrives in the order it
    happened rather than newest-first.
    """

    moment = now or datetime.now(
        timezone.utc,
    )

    rows = session.scalars(
        select(
            PollSessionRecord,
        ).where(
            PollSessionRecord.notified_at.is_(
                None,
            ),
            PollSessionRecord.qualifying_discovered > 0,
        ).order_by(
            PollSessionRecord.started_at,
        )
    ).all()

    ready = []

    for row in rows:
        closed_at = _as_utc(
            row.started_at,
        ) + SESSION_BUCKET

        # Still being written to: the pull is still arriving.
        if closed_at > moment:
            continue

        ready.append(
            row,
        )

    return ready


def qualifying_jobs(
    session: Session,
    pull: PollSessionRecord,
) -> list[tuple[JobRecord, JobEvaluationRecord, int | None]]:
    """The gate-passing jobs this pull discovered, best signal first.

    Carries the resume match where there is one. Unscored is common and
    is not a low score: it means the posting was never readable, and
    the email says so rather than printing a zero.
    """

    active_resume = session.scalar(
        select(
            ResumeRecord.id,
        ).where(
            ResumeRecord.is_active.is_(True),
        )
    )

    rows = session.execute(
        select(
            JobRecord,
            JobEvaluationRecord,
            JobResumeScoreRecord.score,
        ).join(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id == JobRecord.id,
        ).outerjoin(
            JobResumeScoreRecord,
            (
                JobResumeScoreRecord.job_id == JobRecord.id
            )
            & (
                JobResumeScoreRecord.resume_id == active_resume
            ),
        ).where(
            JobRecord.first_seen_session_id == pull.id,
            JobEvaluationRecord.eligibility_status == "PASS",
        ).order_by(
            # The same order the queue leads with: roles that announce
            # themselves as new grad, then the strongest resume match,
            # then the ones ACE could actually read.
            JobEvaluationRecord.is_new_grad.desc(),
            JobResumeScoreRecord.score.desc().nullslast(),
            JobEvaluationRecord.requirements_verified.desc(),
            JobRecord.company,
        )
    ).all()

    return [
        (
            row[0],
            row[1],
            row[2],
        )
        for row in rows
    ]


def _experience(
    evaluation: JobEvaluationRecord,
) -> str:
    """How the row states experience, in the interface's three states."""

    if evaluation.is_early_career:
        return "Early career"

    if evaluation.required_experience_years is not None:
        return (
            f"{evaluation.required_experience_years} yrs max"
        )

    return "Experience not stated"


def render(
    pull: PollSessionRecord,
    jobs: list[tuple[JobRecord, JobEvaluationRecord]],
) -> tuple[str, str]:
    """Return the subject and body for one pull."""

    count = len(
        jobs,
    )

    subject = (
        f"ACE: {count} new "
        + (
            "opportunity"
            if count == 1
            else "opportunities"
        )
    )

    lines = [
        f"{count} new "
        + (
            "role"
            if count == 1
            else "roles"
        )
        + " passed your filters.",
        "",
    ]

    for job, evaluation, _score in jobs[:MAX_LISTED]:
        lines.append(
            f"{job.company} - {job.title}",
        )

        lines.append(
            "  "
            + " | ".join(
                part
                for part in (
                    job.location,
                    _experience(
                        evaluation,
                    ),
                )
                if part
            ),
        )

        # The employer's own posting, never an aggregator or a link
        # back into ACE. Tapping it on a phone has to land on the
        # application form, which is the entire point of the email.
        lines.append(
            "  " + job.official_url,
        )

        lines.append(
            "",
        )

    if count > MAX_LISTED:
        lines.append(
            f"and {count - MAX_LISTED} more, "
            "in the queue.",
        )

        lines.append(
            "",
        )

    settings = get_settings()

    lines.append(
        settings.public_base_url.rstrip(
            "/",
        )
        + "/",
    )

    return subject, "\n".join(
        lines,
    )


def _escape(
    value: str,
) -> str:
    """Minimal HTML escaping for values that came from an employer."""

    return (
        str(
            value or "",
        )
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ACE's own palette. Stated as hex rather than variables because email
# clients do not support custom properties, and repeated inline rather
# than in a stylesheet because Gmail strips <style> in some contexts.
INK = "#f4f0fa"
MUTED = "#b3a3cd"
CANVAS = "#0f0a17"
CARD = "#1c1229"
LINE = "#33244a"
GOLD = "#c9a227"
PURPLE = "#8b6fc7"


def _tier_badge(
    company: str,
) -> str:
    """The employer tier chip, or nothing for an unclassified name."""

    tier = classify_company(
        company,
    )

    label = {
        CompanyTier.BIG_TECH: "BIG TECH",
        CompanyTier.TOP_TIER: "TOP TIER",
        CompanyTier.ESTABLISHED: "ESTABLISHED",
    }.get(
        tier,
    )

    if not label:
        return ""

    colour = (
        GOLD
        if tier is CompanyTier.BIG_TECH
        else PURPLE
    )

    return (
        '<span style="display:inline-block;margin-left:8px;'
        "padding:2px 7px;border-radius:4px;font-size:10px;"
        "letter-spacing:.08em;font-weight:700;"
        f'color:{colour};border:1px solid {colour};">'
        f"{label}</span>"
    )


def _score_chip(
    score: int | None,
) -> str:
    """The resume match, or an honest statement that there is none.

    Unscored is not a low score: it means the posting was never
    readable. Printing a zero would be a lie about what ACE knows.
    """

    if score is None:
        return (
            f'<span style="color:{MUTED};font-size:12px;'
            'font-style:italic;">Not scored</span>'
        )

    tier = (
        "HIGH"
        if score >= 70
        else "MEDIUM"
        if score >= 45
        else "MINIMAL"
    )

    colour = (
        GOLD
        if score >= 70
        else INK
        if score >= 45
        else MUTED
    )

    return (
        f'<span style="color:{colour};font-size:12px;'
        'font-weight:700;letter-spacing:.06em;">'
        f"{tier} {score}</span>"
    )


def render_html(
    pull: PollSessionRecord,
    jobs: list,
) -> str:
    """The alert as HTML.

    Tables and inline styles throughout, because email clients are not
    browsers: Gmail strips much of a <style> block, Outlook renders
    through Word, and neither supports flexbox or grid. A 600px table
    is the layout that has worked everywhere for twenty years.

    Every colour is stated explicitly, including on the outermost
    wrapper, because a client that assumes a white page behind
    transparent content turns light text invisible.
    """

    count = len(
        jobs,
    )

    settings = get_settings()

    base = settings.public_base_url.rstrip(
        "/",
    )

    # What the inbox shows beside the subject line, before the mail is
    # opened. Left out, a client scrapes the first text in the body,
    # which is the wordmark, so every alert previews as "A C E".
    preheader = _escape(
        ", ".join(
            f"{job.company} {job.title}"[:48]
            for job, _evaluation, _score in jobs[:3]
        )
    )

    cards = []

    for job, evaluation, score in jobs[:MAX_LISTED]:
        facts = " &middot; ".join(
            _escape(
                part,
            )
            for part in (
                job.location,
                _experience(
                    evaluation,
                ),
            )
            if part
        )

        cards.append(
            f"""
<tr><td style="padding:0 0 12px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         bgcolor="{CARD}"
         style="background:{CARD};border:1px solid {LINE};border-radius:12px;">
    <tr><td style="padding:18px 20px;">
      <div style="font-size:13px;font-weight:600;color:{MUTED};
                  padding-bottom:6px;">
        {_escape(job.company)}{_tier_badge(job.company)}
      </div>
      <div style="padding-bottom:10px;">
        <a href="{_escape(job.official_url)}"
           style="color:{INK};font-size:17px;font-weight:600;
                  text-decoration:none;line-height:1.35;">
          {_escape(job.title)}
        </a>
      </div>
      <div style="font-size:12.5px;color:{MUTED};padding-bottom:14px;">
        {facts}
      </div>
      <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
        <tr>
          <td align="left" style="vertical-align:middle;">
            {_score_chip(score)}
          </td>
          <td align="right">
            <table role="presentation" cellpadding="0" cellspacing="0"
                   border="0" style="display:inline-block;">
              <tr><td bgcolor="{GOLD}" align="center"
                      style="background:{GOLD};border-radius:7px;">
                <a href="{_escape(job.official_url)}"
                   style="display:block;color:#231633;font-size:13px;
                          font-weight:700;text-decoration:none;
                          padding:10px 20px;font-family:Arial,Helvetica,
                          sans-serif;">Apply</a>
              </td></tr>
            </table>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</td></tr>"""
        )

    more = ""

    if count > MAX_LISTED:
        more = (
            f'<tr><td style="padding:4px 0 16px 0;color:{MUTED};'
            'font-size:13px;text-align:center;">'
            f"and {count - MAX_LISTED} more in the queue"
            "</td></tr>"
        )

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<!-- Without this a phone lays the mail out at ~980px and zooms out,
     which is how an email becomes unreadable on the device it was
     written for. The whole point of alerting is applying from a
     phone. -->
<meta name="viewport" content="width=device-width,initial-scale=1">
<!-- Tells a client the mail is designed dark, so it does not invert
     the palette and leave light text on a light card. -->
<meta name="color-scheme" content="dark light">
<meta name="supported-color-schemes" content="dark light">
<title>ACE</title>
</head>
<body style="margin:0;padding:0;background:{CANVAS};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       bgcolor="{CANVAS}"
       style="background:{CANVAS};padding:28px 12px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
       style="width:100%;max-width:600px;
              font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',
                          Roboto,Helvetica,Arial,sans-serif;">

  <tr><td style="font-size:0;line-height:0;max-height:0;
                 mso-hide:all;overflow:hidden;color:{CANVAS};">
    {preheader}
  </td></tr>

  <tr><td style="padding:0 0 22px 0;">
    <div style="font-size:15px;font-weight:700;letter-spacing:.18em;
                color:{INK};">A C E</div>
    <div style="font-size:22px;font-weight:600;color:{INK};
                padding-top:12px;">
      {count} new {"opportunity" if count == 1 else "opportunities"}
    </div>
    <div style="font-size:13px;color:{MUTED};padding-top:4px;">
      Passed your filters in this pull.
    </div>
  </td></tr>

  {"".join(cards)}
  {more}

  <tr><td style="padding:10px 0 0 0;border-top:1px solid {LINE};">
    <div style="padding-top:16px;font-size:12px;color:{MUTED};">
      <a href="{base}/" style="color:{PURPLE};text-decoration:none;">
        Open the full queue
      </a>
    </div>
  </td></tr>

</table>
</td></tr></table>
</body></html>"""


def send_pending(
    session: Session,
    *,
    now: datetime | None = None,
) -> int:
    """Alert every finished pull that has not been alerted. Returns how
    many emails were sent.

    Marks a pull notified whether or not the send succeeded. The
    alternative is retrying, and a pull that could not be delivered
    once is stale by the time a retry would land: the jobs are still in
    the queue, which is the durable surface. An alert is a nudge, not a
    record.
    """

    settings = get_settings()

    if not settings.alert_email:
        return 0

    moment = now or datetime.now(
        timezone.utc,
    )

    sent = 0

    for pull in pending_pulls(
        session,
        now=moment,
    ):
        age = moment - _as_utc(
            pull.started_at,
        )

        jobs = qualifying_jobs(
            session,
            pull,
        )

        if age > MAX_AGE or not jobs:
            # Too old to be useful, or the qualifying count was
            # recorded but the jobs have since been re-evaluated away.
            # Marked so it is not reconsidered every cycle.
            pull.notified_at = moment
            continue

        subject, body = render(
            pull,
            jobs,
        )

        delivered = send_mail(
            to=settings.alert_email,
            subject=subject,
            text=body,
            html=render_html(
                pull,
                jobs,
            ),
        )

        pull.notified_at = moment

        if delivered:
            sent += 1

        LOGGER.info(
            "alert_pull id=%s jobs=%s delivered=%s",
            pull.id,
            len(
                jobs,
            ),
            delivered,
        )

    return sent
