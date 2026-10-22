"""Google identity tokens are accepted only after every OIDC check passes."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from backend.app.auth.google import GoogleAuthError, verify_id_token


NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
CLIENT_ID = "fictional-client.apps.googleusercontent.com"
NONCE = "one-time-browser-nonce"


def _part(value: object) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _integer(value: int) -> str:
    size = (value.bit_length() + 7) // 8
    return (
        base64.urlsafe_b64encode(value.to_bytes(size, "big"))
        .rstrip(b"=")
        .decode()
    )


def _token(**changes):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_numbers()
    header = {"alg": "RS256", "kid": "test-key", "typ": "JWT"}
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-owner-subject",
        "email": "OWNER@EXAMPLE.COM",
        "name": "Alex Rivera",
        "email_verified": True,
        "nonce": NONCE,
        "iat": int(NOW.timestamp()) - 10,
        "exp": int(NOW.timestamp()) + 300,
        **changes,
    }
    unsigned = f"{_part(header)}.{_part(claims)}"
    signature = private.sign(unsigned.encode(), padding.PKCS1v15(), hashes.SHA256())
    token = f"{unsigned}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"
    jwks = {
        "keys": [
            {
                "kid": "test-key",
                "kty": "RSA",
                "n": _integer(public.n),
                "e": _integer(public.e),
            }
        ]
    }
    return token, jwks


def test_verified_google_owner_identity_is_accepted() -> None:
    token, keys = _token()
    identity = verify_id_token(
        token,
        jwks=keys,
        client_id=CLIENT_ID,
        nonce=NONCE,
        now=NOW,
    )
    assert identity.subject == "google-owner-subject"
    assert identity.email == "owner@example.com"
    assert identity.name == "Alex Rivera"


@pytest.mark.parametrize(
    "change,nonce",
    [
        ({"aud": "another-client"}, NONCE),
        ({"email_verified": False}, NONCE),
        ({"exp": int(NOW.timestamp()) - 500}, NONCE),
        ({"nonce": "another-browser"}, NONCE),
    ],
)
def test_untrusted_google_claims_are_rejected(change, nonce) -> None:
    token, keys = _token(**change)
    with pytest.raises(GoogleAuthError):
        verify_id_token(
            token,
            jwks=keys,
            client_id=CLIENT_ID,
            nonce=nonce,
            now=NOW,
        )


def test_a_token_signed_by_another_key_is_rejected() -> None:
    token, _ = _token()
    _, other_keys = _token()
    with pytest.raises(GoogleAuthError):
        verify_id_token(
            token,
            jwks=other_keys,
            client_id=CLIENT_ID,
            nonce=NONCE,
            now=NOW,
        )
