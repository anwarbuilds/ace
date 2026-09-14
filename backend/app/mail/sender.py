"""Send one email, or say where it would have gone.

ACE deleted its entire email subsystem on 2026-09-06: outbox, digests,
SMTP, delivery worker, roughly 4,000 lines. This does not bring any of
that back. It is one HTTPS call with no queue, no retries and no
persistence, because a password reset that fails should be retried by
the person clicking the button, not by a background worker holding
their address for a week.

An HTTPS API is used rather than SMTP because cloud providers routinely
block outbound port 25 and 587, which is where self-hosted SMTP quietly
dies.
"""

from __future__ import annotations

import logging

import httpx

from backend.app.config import get_settings


LOGGER = logging.getLogger(
    "ace.mail",
)

RESEND_ENDPOINT = "https://api.resend.com/emails"

TIMEOUT_SECONDS = 10.0


def send(
    *,
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
) -> bool:
    """Send one message. Returns whether it actually left.

    With no API key configured the message is logged instead. That is
    deliberate rather than a stub: it keeps a self-hosted instance
    recoverable without a mail provider, and it is how the reset flow
    is exercised in development. The caller must not tell the user the
    difference, or the response becomes an oracle for which addresses
    have accounts.
    """

    settings = get_settings()

    if not settings.resend_api_key:
        LOGGER.warning(
            "mail_not_configured to=%s subject=%s\n%s",
            to,
            subject,
            text,
        )

        return False

    try:
        response = httpx.post(
            RESEND_ENDPOINT,
            headers={
                "Authorization": (
                    "Bearer "
                    + settings.resend_api_key
                ),
            },
            json={
                "from": settings.mail_from,
                "to": [
                    to,
                ],
                "subject": subject,
                # Both parts, always. A client that refuses HTML, a
                # screen reader, and a plain-text preview all fall back
                # to the text version, and a mail with only HTML in it
                # is more likely to be treated as spam.
                "text": text,
                **(
                    {
                        "html": html,
                    }
                    if html
                    else {}
                ),
            },
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as error:
        LOGGER.error(
            "mail_failed to=%s error=%s",
            to,
            error,
        )

        return False

    if response.status_code >= 400:
        LOGGER.error(
            "mail_rejected to=%s status=%s body=%s",
            to,
            response.status_code,
            response.text[:400],
        )

        return False

    return True
