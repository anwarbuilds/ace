"""Signing in, staying signed in, and signing out.

Sessions are rows rather than self-contained signed cookies, so that
signing out, or losing a laptop, can actually end them. A stateless
cookie cannot be revoked without keeping a list of the ones you have
revoked, which is this table with extra steps.
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
    verify_password,
)
from backend.app.db.models import (
    AuthSessionRecord,
    UserRecord,
)


# How long a session can live at all, however actively it is used.
ABSOLUTE_LIFETIME = timedelta(
    days=30,
)

# How long it can sit unused. Both are enforced: an absolute cap alone
# lets a stolen cookie run for a month, and an idle cap alone lets one
# run forever so long as it is used.
IDLE_LIFETIME = timedelta(
    days=14,
)

# Verifying a password against an account that does not exist must cost
# the same as verifying against one that does, or the response time
# answers "is this person a user here" for anyone who asks.
_TIMING_DECOY = hash_password(
    "timing-decoy-never-a-real-password",
)


def _as_utc(
    value: datetime,
) -> datetime:
    """Read a stored timestamp as UTC-aware.

    PostgreSQL hands back an aware datetime; SQLite, which the tests
    run on, drops the zone and hands back a naive one. Comparing the
    two raises, so every timestamp read from a row goes through here
    rather than being trusted to carry its zone.
    """

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc,
        )

    return value


def authenticate(
    session: Session,
    email: str,
    password: str,
) -> UserRecord | None:
    """Return the account for these credentials, or None."""

    wanted = (email or "").strip().lower()

    user = session.scalar(
        select(
            UserRecord,
        ).where(
            UserRecord.email == wanted,
        )
    )

    if user is None:
        # Deliberately still pays the cost of a verification.
        verify_password(
            password or "",
            _TIMING_DECOY,
        )

        return None

    if not verify_password(
        password or "",
        user.password_hash,
    ):
        return None

    return user


def start_session(
    session: Session,
    user: UserRecord,
    *,
    now: datetime | None = None,
) -> str:
    """Open a session and return the token to hand to the browser.

    The token is returned once and never stored. Only its fingerprint
    is kept, so the table cannot be read back into live sessions.
    """

    moment = now or datetime.now(
        timezone.utc,
    )

    token = new_session_token()

    session.add(
        AuthSessionRecord(
            token_fingerprint=token_fingerprint(
                token,
            ),
            user_id=user.id,
            created_at=moment,
            expires_at=moment + ABSOLUTE_LIFETIME,
            last_seen_at=moment,
        )
    )

    user.last_login_at = moment

    return token


def resolve_session(
    session: Session,
    token: str | None,
    *,
    now: datetime | None = None,
) -> UserRecord | None:
    """Return the signed-in account for a token, or None.

    Rolls `last_seen_at` forward, which is what makes the idle timeout
    mean anything.
    """

    if not token:
        return None

    moment = now or datetime.now(
        timezone.utc,
    )

    record = session.get(
        AuthSessionRecord,
        token_fingerprint(
            token,
        ),
    )

    if record is None:
        return None

    if _as_utc(record.expires_at) <= moment:
        session.delete(
            record,
        )

        return None

    if _as_utc(record.last_seen_at) + IDLE_LIFETIME <= moment:
        session.delete(
            record,
        )

        return None

    record.last_seen_at = moment

    return session.get(
        UserRecord,
        record.user_id,
    )


def end_session(
    session: Session,
    token: str | None,
) -> None:
    """Sign out one browser."""

    if not token:
        return

    record = session.get(
        AuthSessionRecord,
        token_fingerprint(
            token,
        ),
    )

    if record is not None:
        session.delete(
            record,
        )


def purge_expired(
    session: Session,
    *,
    now: datetime | None = None,
) -> int:
    """Delete sessions past either limit. Returns how many."""

    moment = now or datetime.now(
        timezone.utc,
    )

    result = session.execute(
        delete(
            AuthSessionRecord,
        ).where(
            (AuthSessionRecord.expires_at <= moment)
            | (
                AuthSessionRecord.last_seen_at
                <= moment - IDLE_LIFETIME
            ),
        )
    )

    return result.rowcount or 0
