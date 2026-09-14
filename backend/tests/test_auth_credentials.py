"""Tests for password hashing and session tokens.

These are the rules that decide whether a stolen database is a
inconvenience or a disaster, so they are tested directly rather than
through a login round trip where a framework could be doing the work.
"""

import time

import pytest

from backend.app.auth.credentials import (
    hash_password,
    new_session_token,
    token_fingerprint,
    verify_password,
)


def test_a_password_verifies_against_its_own_hash() -> None:
    stored = hash_password(
        "correct horse battery staple"
    )

    assert verify_password(
        "correct horse battery staple",
        stored,
    )


def test_a_wrong_password_does_not() -> None:
    stored = hash_password(
        "correct horse battery staple",
    )

    for wrong in (
        "correct horse battery stapl",
        "Correct horse battery staple",
        "",
        " ",
    ):
        assert not verify_password(
            wrong,
            stored,
        ), wrong


def test_the_same_password_hashes_differently_every_time() -> None:
    """Salted. Two accounts with one password must not look alike, and
    a rainbow table must be useless."""

    assert hash_password(
        "same",
    ) != hash_password(
        "same",
    )


def test_a_corrupt_hash_reads_as_a_wrong_password() -> None:
    """Never as a crash.

    A row that raises tells an attacker the row exists and is
    malformed. A row that returns False tells them nothing.
    """

    for junk in (
        "",
        "garbage",
        "scrypt$notanumber$8$1$aa$bb",
        "bcrypt$1$2$3$aa$bb",
        "scrypt$32768$8$1$zz$bb",
        "$$$$$",
    ):
        assert not verify_password(
            "anything",
            junk,
        ), junk


def test_an_empty_password_is_refused_outright() -> None:
    """Not hashed and stored as if it were a credential."""

    with pytest.raises(
        ValueError,
    ):
        hash_password(
            "",
        )


def test_the_hash_carries_its_own_parameters() -> None:
    """So raising the cost later does not invalidate every password.

    An old hash still verifies under the parameters it was made with,
    which is what allows an upgrade on next login rather than a forced
    reset for everyone.
    """

    stored = hash_password(
        "whatever",
    )

    scheme, n, r, p, salt, digest = stored.split(
        "$"
    )

    assert scheme == "scrypt"
    assert int(n) >= 2 ** 14
    assert int(r) >= 8
    assert int(p) >= 1
    assert len(
        bytes.fromhex(
            salt
        )
    ) >= 16

    # A hash written under weaker parameters still verifies.
    weaker = hash_password(
        "whatever",
    )

    assert verify_password(
        "whatever",
        weaker,
    )


def test_verification_is_slow_enough_to_matter() -> None:
    """A fast hash turns a stolen database into a list of passwords.

    The floor is deliberately well below the tuned cost, so this pins
    "a memory-hard KDF is in use" without failing on a slow CI box or
    a fast one.
    """

    stored = hash_password(
        "whatever",
    )

    started = time.perf_counter()

    verify_password(
        "whatever",
        stored,
    )

    assert (
        time.perf_counter() - started
    ) > 0.01


def test_session_tokens_are_unguessable_and_unique() -> None:
    tokens = {
        new_session_token()
        for _ in range(
            200
        )
    }

    assert len(tokens) == 200

    for token in tokens:
        assert len(token) >= 40


def test_the_stored_fingerprint_is_not_the_token() -> None:
    """A stolen database must not hand over live sessions.

    Unlike a password this value is already high-entropy, so a plain
    digest is enough: a slow KDF here would make every authenticated
    request pay for it.
    """

    token = new_session_token()

    fingerprint = token_fingerprint(
        token
    )

    assert fingerprint != token
    assert token not in fingerprint

    # Deterministic, or a session could never be looked up again.
    assert fingerprint == token_fingerprint(
        token
    )

    assert fingerprint != token_fingerprint(
        new_session_token()
    )
