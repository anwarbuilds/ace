"""Tests for signing in and staying signed in."""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.auth.credentials import (
    hash_password,
    token_fingerprint,
)
from backend.app.auth.service import (
    ABSOLUTE_LIFETIME,
    IDLE_LIFETIME,
    authenticate,
    end_session,
    purge_expired,
    resolve_session,
    start_session,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    AuthSessionRecord,
    UserRecord,
)


NOW = datetime(
    2026,
    9,
    13,
    12,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture(name="session")
def fixture_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
    )

    Base.metadata.create_all(
        engine
    )

    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    with factory() as session:
        session.add(
            UserRecord(
                email="owner@example.com",
                password_hash=hash_password(
                    "a-long-enough-password",
                ),
            )
        )

        session.flush()

        yield session


def _owner(
    session,
) -> UserRecord:
    return session.scalars(
        UserRecord.__table__.select()
    ).first() and session.get(
        UserRecord,
        1,
    )


def test_correct_credentials_return_the_account(
    session,
) -> None:
    assert authenticate(
        session,
        "owner@example.com",
        "a-long-enough-password",
    ) is not None


def test_the_email_is_matched_case_insensitively(
    session,
) -> None:
    """Nobody remembers how they capitalised their own address."""

    assert authenticate(
        session,
        "  Owner@Example.COM ",
        "a-long-enough-password",
    ) is not None


def test_wrong_password_and_unknown_account_both_return_none(
    session,
) -> None:
    assert authenticate(
        session,
        "owner@example.com",
        "wrong",
    ) is None

    assert authenticate(
        session,
        "nobody@example.com",
        "a-long-enough-password",
    ) is None


def test_a_session_token_is_not_stored(
    session,
) -> None:
    """A stolen database must not hand over live sessions."""

    token = start_session(
        session,
        _owner(session),
        now=NOW,
    )

    session.flush()

    stored = session.scalars(
        AuthSessionRecord.__table__.select()
    ).all()

    rows = session.query(
        AuthSessionRecord
    ).all()

    assert len(rows) == 1
    assert rows[0].token_fingerprint != token
    assert rows[0].token_fingerprint == token_fingerprint(
        token
    )


def test_a_live_token_resolves_to_its_account(
    session,
) -> None:
    token = start_session(
        session,
        _owner(session),
        now=NOW,
    )

    session.flush()

    user = resolve_session(
        session,
        token,
        now=NOW + timedelta(minutes=5),
    )

    assert user is not None
    assert user.email == "owner@example.com"


def test_nothing_resolves_for_a_missing_or_junk_token(
    session,
) -> None:
    for token in (
        None,
        "",
        "not-a-real-token",
    ):
        assert resolve_session(
            session,
            token,
            now=NOW,
        ) is None


def test_a_session_dies_at_its_absolute_limit(
    session,
) -> None:
    """However actively it has been used.

    An idle cap alone lets a stolen cookie run forever so long as it
    keeps being used.
    """

    token = start_session(
        session,
        _owner(session),
        now=NOW,
    )

    session.flush()

    # Used constantly right up to the limit.
    moment = NOW

    for _ in range(5):
        moment = moment + (ABSOLUTE_LIFETIME / 6)

        assert resolve_session(
            session,
            token,
            now=moment,
        ) is not None

    assert resolve_session(
        session,
        token,
        now=NOW + ABSOLUTE_LIFETIME + timedelta(seconds=1),
    ) is None


def test_a_session_dies_after_sitting_unused(
    session,
) -> None:
    token = start_session(
        session,
        _owner(session),
        now=NOW,
    )

    session.flush()

    assert resolve_session(
        session,
        token,
        now=NOW + IDLE_LIFETIME + timedelta(seconds=1),
    ) is None


def test_using_a_session_keeps_it_alive(
    session,
) -> None:
    """Which is the whole point of rolling last_seen_at forward."""

    token = start_session(
        session,
        _owner(session),
        now=NOW,
    )

    session.flush()

    halfway = NOW + (IDLE_LIFETIME / 2)

    assert resolve_session(
        session,
        token,
        now=halfway,
    ) is not None

    # Would have expired had the visit above not counted.
    assert resolve_session(
        session,
        token,
        now=halfway + (IDLE_LIFETIME / 2) + timedelta(hours=1),
    ) is not None


def test_signing_out_ends_that_session(
    session,
) -> None:
    token = start_session(
        session,
        _owner(session),
        now=NOW,
    )

    session.flush()

    end_session(
        session,
        token,
    )

    session.flush()

    assert resolve_session(
        session,
        token,
        now=NOW,
    ) is None


def test_signing_out_does_not_end_the_others(
    session,
) -> None:
    """Signing out of a borrowed laptop must not sign out your phone."""

    keep = start_session(
        session,
        _owner(session),
        now=NOW,
    )

    drop = start_session(
        session,
        _owner(session),
        now=NOW,
    )

    session.flush()

    end_session(
        session,
        drop,
    )

    session.flush()

    assert resolve_session(
        session,
        keep,
        now=NOW,
    ) is not None


def test_expired_sessions_are_purgeable(
    session,
) -> None:
    start_session(
        session,
        _owner(session),
        now=NOW,
    )

    session.flush()

    assert purge_expired(
        session,
        now=NOW,
    ) == 0

    assert purge_expired(
        session,
        now=NOW + ABSOLUTE_LIFETIME + timedelta(days=1),
    ) == 1
