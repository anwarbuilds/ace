"""Hashing and token generation, in one place so it is reviewed once.

Passwords use argon2id with the library's defaults, which follow RFC
9106's second recommended profile (64 MiB, 3 passes, 4 lanes). Tokens
are 256 random bits; only their SHA-256 is stored, which is enough for
a value that is already unguessable and lets lookup be an index hit.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)


HASHER = PasswordHasher()

MIN_PASSWORD_LENGTH = 12

MAX_PASSWORD_LENGTH = 256

# Pairing codes are typed by hand from one screen into another, so they
# use an alphabet without look-alikes (no I, L, O, U, 0 or 1).
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"

CODE_LENGTH = 8

# A hash checked when the email matches no account, so a wrong address
# costs the same time as a wrong password and timing does not reveal
# which addresses exist.
_DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(16))


class WeakPassword(ValueError):
    """The password fails the policy; the message says why."""


def check_password_policy(password: str, *, email: str = "") -> None:
    """Length is the rule that matters (NIST SP 800-63B); no composition
    rules, which mostly produce predictable substitutions."""

    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPassword(
            f"Use at least {MIN_PASSWORD_LENGTH} characters."
        )

    if len(password) > MAX_PASSWORD_LENGTH:
        raise WeakPassword(
            f"Use at most {MAX_PASSWORD_LENGTH} characters."
        )

    if email and password.strip().lower() == email.strip().lower():
        raise WeakPassword("The password cannot be the email address.")


def hash_password(password: str) -> str:
    return HASHER.hash(password)


def verify_password(stored: str | None, password: str) -> bool:
    """Constant work whether or not there is a stored hash."""

    try:
        return HASHER.verify(stored or _DUMMY_HASH, password) and bool(stored)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored: str) -> bool:
    return HASHER.check_needs_rehash(stored)


def new_token(prefix: str = "") -> str:
    return prefix + secrets.token_urlsafe(32)


def new_code() -> str:
    return "".join(
        secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH)
    )


def normalise_code(code: str) -> str:
    """Accept the code the way people type it: any case, with spaces."""

    return "".join(ch for ch in code.upper() if ch.isalnum())


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
