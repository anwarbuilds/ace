"""Tests for password reset.

A reset link is a credential: anyone holding one can take the account.
These pin the rules that keep that survivable.
"""

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
    verify_password,
)
from backend.app.auth.reset import (
    LIFETIME,
    check,
    issue,
    spend,
)
from backend.app.auth.service import (
    resolve_session,
    start_session,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    PasswordResetRecord,
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
                id=1,
                email="owner@example.com",
                password_hash=hash_password(
                    "the-original-password",
                ),
            )
        )

        session.flush()

        yield session


def test_an_unknown_address_yields_nothing(
    session,
) -> None:
    """And the caller must answer identically either way.

    Anything else turns the reset form into a way to ask which
    addresses have accounts here.
    """

    assert issue(
        session,
        "nobody@example.com",
        now=NOW,
    ) is None


def test_a_known_address_yields_a_token_that_is_not_stored(
    session,
) -> None:
    result = issue(
        session,
        "owner@example.com",
        now=NOW,
    )

    assert result is not None

    user, token = result

    session.flush()

    rows = session.query(
        PasswordResetRecord
    ).all()

    assert len(rows) == 1
    assert rows[0].token_fingerprint != token
    assert rows[0].token_fingerprint == token_fingerprint(
        token
    )


def test_the_address_is_matched_case_insensitively(
    session,
) -> None:
    assert issue(
        session,
        "  Owner@Example.COM ",
        now=NOW,
    ) is not None


def test_a_fresh_token_checks_out(
    session,
) -> None:
    _, token = issue(
        session,
        "owner@example.com",
        now=NOW,
    )

    session.flush()

    record, why = check(
        session,
        token,
        now=NOW + timedelta(minutes=5),
    )

    assert record is not None
    assert why == "ok"


def test_an_expired_token_is_refused(
    session,
) -> None:
    _, token = issue(
        session,
        "owner@example.com",
        now=NOW,
    )

    session.flush()

    record, why = check(
        session,
        token,
        now=NOW + LIFETIME + timedelta(seconds=1),
    )

    assert record is None
    assert why == "expired"


def test_a_junk_token_is_refused(
    session,
) -> None:
    for token in (
        None,
        "",
        "not-a-real-token",
    ):
        record, why = check(
            session,
            token,
            now=NOW,
        )

        assert record is None
        assert why == "invalid"


def test_a_token_works_exactly_once(
    session,
) -> None:
    """A mail client that prefetches the link must not consume it in a
    way that leaves the user with no explanation."""

    _, token = issue(
        session,
        "owner@example.com",
        now=NOW,
    )

    session.flush()

    record, _ = check(
        session,
        token,
        now=NOW,
    )

    spend(
        session,
        record,
        "a-brand-new-password",
        now=NOW,
    )

    session.flush()

    again, why = check(
        session,
        token,
        now=NOW,
    )

    assert again is None

    # "used", not "invalid": the difference between a clear message and
    # a confusing one.
    assert why == "used"


def test_spending_a_token_changes_the_password(
    session,
) -> None:
    _, token = issue(
        session,
        "owner@example.com",
        now=NOW,
    )

    session.flush()

    record, _ = check(
        session,
        token,
        now=NOW,
    )

    user = spend(
        session,
        record,
        "a-brand-new-password",
        now=NOW,
    )

    assert verify_password(
        "a-brand-new-password",
        user.password_hash,
    )

    assert not verify_password(
        "the-original-password",
        user.password_hash,
    )


def test_a_reset_ends_every_session(
    session,
) -> None:
    """Including any the attacker opened.

    A reset happens because control of the account is in question.
    Leaving live cookies alive would answer the wrong question.
    """

    user = session.get(
        UserRecord,
        1,
    )

    existing = start_session(
        session,
        user,
        now=NOW,
    )

    session.flush()

    assert resolve_session(
        session,
        existing,
        now=NOW,
    ) is not None

    _, token = issue(
        session,
        "owner@example.com",
        now=NOW,
    )

    session.flush()

    record, _ = check(
        session,
        token,
        now=NOW,
    )

    spend(
        session,
        record,
        "a-brand-new-password",
        now=NOW,
    )

    session.flush()

    assert resolve_session(
        session,
        existing,
        now=NOW,
    ) is None


def test_requesting_again_invalidates_the_earlier_link(
    session,
) -> None:
    """Two live links means two chances for an old one to be found."""

    _, first = issue(
        session,
        "owner@example.com",
        now=NOW,
    )

    session.flush()

    _, second = issue(
        session,
        "owner@example.com",
        now=NOW + timedelta(minutes=1),
    )

    session.flush()

    assert check(
        session,
        first,
        now=NOW + timedelta(minutes=2),
    )[0] is None

    assert check(
        session,
        second,
        now=NOW + timedelta(minutes=2),
    )[0] is not None
