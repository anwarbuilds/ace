"""Password hashing and session tokens.

Pure functions over strings and bytes. No database, no framework, no
clock beyond what is passed in, so the rules here can be tested
directly rather than through a login round trip.

`hashlib.scrypt` is used rather than a dependency. It is a memory-hard
KDF in the standard library, which is the whole requirement: the thing
that must not happen is a fast hash, because a fast hash turns a stolen
database into a list of passwords.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


# Tuned so one verification costs roughly 100ms on a small cloud
# instance. That is unnoticeable on a login form and expensive enough
# that guessing offline is not worth starting.
SCRYPT_N = 2 ** 15

SCRYPT_R = 8

SCRYPT_P = 1

SALT_BYTES = 16

# scrypt needs 128 * N * r bytes, which at these parameters is exactly
# 32 MB -- and OpenSSL's default ceiling is also exactly 32 MB, so it
# refuses by a hair. Stated explicitly rather than tuned down, because
# the memory cost is the point of choosing scrypt.
SCRYPT_MAXMEM = 128 * SCRYPT_N * SCRYPT_R * 2

# 32 bytes of entropy. The token is what a stolen cookie *is*, so it
# has to be unguessable on its own rather than a lookup key that
# something else protects.
TOKEN_BYTES = 32


def hash_password(
    password: str,
) -> str:
    """Return a self-describing hash: algorithm, cost, salt, digest.

    The parameters travel with the hash so raising the cost later does
    not invalidate every existing password. An old hash still verifies
    under its own parameters, and can be upgraded on next login.
    """

    if not password:
        raise ValueError(
            "password must not be empty"
        )

    salt = secrets.token_bytes(
        SALT_BYTES
    )

    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=SCRYPT_MAXMEM,
    )

    return "$".join(
        [
            "scrypt",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            salt.hex(),
            digest.hex(),
        ]
    )


def verify_password(
    password: str,
    stored: str,
) -> bool:
    """Whether a password matches a stored hash.

    Returns False rather than raising on a malformed hash. A corrupt
    row must read as "wrong password", never as a crash that tells an
    attacker the row exists.
    """

    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split(
            "$"
        )

        if scheme != "scrypt":
            return False

        expected = bytes.fromhex(
            digest_hex
        )

        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(
                salt_hex
            ),
            n=int(n),
            r=int(r),
            p=int(p),
            maxmem=128 * int(n) * int(r) * 2,
        )
    except (
        ValueError,
        TypeError,
    ):
        return False

    # Constant time. A timing difference leaks how much of the digest
    # matched, one byte at a time.
    return hmac.compare_digest(
        expected,
        actual,
    )


def new_session_token() -> str:
    """Return a fresh opaque session token."""

    return secrets.token_urlsafe(
        TOKEN_BYTES
    )


def token_fingerprint(
    token: str,
) -> str:
    """Return what gets stored for a session token.

    The token itself is never stored. A stolen database should not hand
    over live sessions as well as password hashes, and unlike a
    password this value is already high-entropy, so a plain SHA-256 is
    enough and a slow KDF would only make every request expensive.
    """

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()
