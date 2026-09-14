"""Password reset: issuing a link, and spending it.

Two rules shape everything here.

A reset link *is* a credential. Anyone holding one can take the
account, so it is short lived, single use, and stored only as a
fingerprint.

And asking for a reset must never reveal whether an address has an
account. The response is identical either way, which is why this module
returns nothing useful to the caller about whether a user was found.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.orm import Session

from backend.app.auth.credentials import (
    hash_password,
    new_session_token,
    token_fingerprint,
)
from backend.app.db.models import (
    AuthSessionRecord,
    PasswordResetRecord,
    UserRecord,
)


# Short, because the link is a credential sitting in an inbox. Long
# enough that a slow mail relay does not hand someone a dead link.
LIFETIME = timedelta(
    hours=1,
)


def _as_utc(
    value: datetime,
) -> datetime:
    """Read a stored timestamp as UTC-aware.

    PostgreSQL returns an aware datetime and SQLite, which the tests
    run on, returns a naive one. Comparing them raises.
    """

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc,
        )

    return value


def issue(
    session: Session,
    email: str,
    *,
    now: datetime | None = None,
) -> tuple[UserRecord, str] | None:
    """Create a reset token for an address, if it has an account.

    Returns None for an unknown address. The caller must answer the
    user identically either way.
    """

    moment = now or datetime.now(
        timezone.utc,
    )

    user = session.scalar(
        select(
            UserRecord,
        ).where(
            UserRecord.email
            == (email or "").strip().lower(),
        )
    )

    if user is None:
        return None

    # Any earlier link is dropped. Two live links means two chances for
    # one to be found in an old inbox, and the most recent request is
    # the one the person is actually waiting on.
    session.execute(
        delete(
            PasswordResetRecord,
        ).where(
            PasswordResetRecord.user_id == user.id,
            PasswordResetRecord.used_at.is_(None),
        )
    )

    token = new_session_token()

    session.add(
        PasswordResetRecord(
            token_fingerprint=token_fingerprint(
                token,
            ),
            user_id=user.id,
            created_at=moment,
            expires_at=moment + LIFETIME,
        )
    )

    return user, token


def check(
    session: Session,
    token: str | None,
    *,
    now: datetime | None = None,
) -> tuple[PasswordResetRecord | None, str]:
    """Return the usable reset row, or why there is not one.

    The reason is for wording the page, not for the caller to act on:
    an expired link and a spent one are both refusals.
    """

    if not token:
        return None, "invalid"

    moment = now or datetime.now(
        timezone.utc,
    )

    record = session.get(
        PasswordResetRecord,
        token_fingerprint(
            token,
        ),
    )

    if record is None:
        return None, "invalid"

    if record.used_at is not None:
        return None, "used"

    if _as_utc(
        record.expires_at,
    ) <= moment:
        return None, "expired"

    return record, "ok"


def spend(
    session: Session,
    record: PasswordResetRecord,
    new_password: str,
    *,
    now: datetime | None = None,
) -> UserRecord:
    """Set the new password and burn the link."""

    moment = now or datetime.now(
        timezone.utc,
    )

    user = session.get(
        UserRecord,
        record.user_id,
    )

    user.password_hash = hash_password(
        new_password,
    )

    record.used_at = moment

    # Every session ends, including any the attacker opened. A reset
    # exists because control of the account is in question, so leaving
    # live cookies alive would answer the wrong question.
    session.execute(
        delete(
            AuthSessionRecord,
        ).where(
            AuthSessionRecord.user_id == user.id,
        )
    )

    return user
