"""Google OpenID Connect for ACE's single owner account.

The browser uses the authorization code flow. ACE requests only
``openid email`` and never receives Google API access beyond identity.
Discovery and signing keys come from Google's published OIDC metadata;
the ID token signature, issuer, audience, expiry, nonce and verified
email are all checked before a local session is created.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from backend.app.auth.crypto import same


DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

ALLOWED_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})

CLOCK_SKEW_SECONDS = 120


class GoogleAuthError(ValueError):
    """Google could not prove the expected owner's identity."""


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str


def configured(client_id: str, client_secret: str, redirect_uri: str) -> bool:
    """Google is available only when the complete server flow is set."""

    return bool(client_id.strip() and client_secret.strip() and redirect_uri.strip())


def authorization_url(
    *,
    endpoint: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    nonce: str,
) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "scope": "openid email",
            "redirect_uri": redirect_uri,
            "state": state,
            "nonce": nonce,
            "prompt": "select_account",
        }
    )
    return f"{endpoint}?{query}"


def authorization_endpoint(*, timeout: float = 10.0) -> str:
    """Read Google's current authorization endpoint from OIDC discovery."""

    try:
        response = httpx.get(DISCOVERY_URL, timeout=timeout)
        response.raise_for_status()
        endpoint = response.json()["authorization_endpoint"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        raise GoogleAuthError("Google sign-in is temporarily unavailable.") from error
    if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
        raise GoogleAuthError("Google sign-in is temporarily unavailable.")
    return endpoint


def _decode_part(value: str) -> bytes:
    value += "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value.encode("ascii"))
    except (ValueError, UnicodeError) as error:
        raise GoogleAuthError("Google returned an invalid identity token.") from error


def _json_part(value: str) -> dict[str, Any]:
    try:
        decoded = json.loads(_decode_part(value))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise GoogleAuthError("Google returned an invalid identity token.") from error
    if not isinstance(decoded, dict):
        raise GoogleAuthError("Google returned an invalid identity token.")
    return decoded


def verify_id_token(
    token: str,
    *,
    jwks: dict[str, Any],
    client_id: str,
    nonce: str,
    now: datetime | None = None,
) -> GoogleIdentity:
    """Verify a Google ID token without trusting any unverified claim."""

    parts = token.split(".")
    if len(parts) != 3:
        raise GoogleAuthError("Google returned an invalid identity token.")
    header = _json_part(parts[0])
    claims = _json_part(parts[1])
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise GoogleAuthError("Google returned an unsupported identity token.")

    key = next(
        (
            candidate
            for candidate in jwks.get("keys", [])
            if isinstance(candidate, dict)
            and candidate.get("kid") == header["kid"]
            and candidate.get("kty") == "RSA"
        ),
        None,
    )
    if key is None:
        raise GoogleAuthError("Google's signing key was not found.")
    try:
        numbers = rsa.RSAPublicNumbers(
            int.from_bytes(_decode_part(str(key["e"])), "big"),
            int.from_bytes(_decode_part(str(key["n"])), "big"),
        )
        public_key = numbers.public_key()
        public_key.verify(
            _decode_part(parts[2]),
            f"{parts[0]}.{parts[1]}".encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except (InvalidSignature, KeyError, TypeError, ValueError) as error:
        raise GoogleAuthError("Google's identity token signature is invalid.") from error

    moment = int((now or datetime.now(timezone.utc)).timestamp())
    issuer = claims.get("iss")
    audience = claims.get("aud")
    audience_ok = audience == client_id or (
        isinstance(audience, list)
        and client_id in audience
        and claims.get("azp") == client_id
    )
    try:
        expiry = int(claims.get("exp", 0))
        issued = int(claims.get("iat", 0))
    except (TypeError, ValueError) as error:
        raise GoogleAuthError("Google returned an invalid identity token.") from error

    if issuer not in ALLOWED_ISSUERS or not audience_ok:
        raise GoogleAuthError("Google returned an identity token for another application.")
    if expiry < moment - CLOCK_SKEW_SECONDS or issued > moment + CLOCK_SKEW_SECONDS:
        raise GoogleAuthError("Google's identity token has expired or is not active yet.")
    if not isinstance(claims.get("nonce"), str) or not same(claims["nonce"], nonce):
        raise GoogleAuthError("Google sign-in could not be matched to this browser.")
    if claims.get("email_verified") is not True:
        raise GoogleAuthError("Google has not verified this email address.")

    subject = claims.get("sub")
    email = claims.get("email")
    if (
        not isinstance(subject, str)
        or not subject
        or not isinstance(email, str)
        or "@" not in email
    ):
        raise GoogleAuthError("Google did not return a usable owner identity.")
    return GoogleIdentity(subject=subject, email=email.strip().lower())


def authenticate(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    nonce: str,
    timeout: float = 10.0,
) -> GoogleIdentity:
    """Exchange one authorization code and verify the returned ID token."""

    try:
        with httpx.Client(timeout=timeout) as client:
            discovery_response = client.get(DISCOVERY_URL)
            discovery_response.raise_for_status()
            discovery = discovery_response.json()
            token_response = client.post(
                discovery["token_endpoint"],
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            token_data = token_response.json()
            jwks_response = client.get(discovery["jwks_uri"])
            jwks_response.raise_for_status()
            jwks = jwks_response.json()
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        raise GoogleAuthError("Google sign-in could not be completed.") from error

    id_token = token_data.get("id_token")
    if not isinstance(id_token, str):
        raise GoogleAuthError("Google did not return an identity token.")
    return verify_id_token(
        id_token,
        jwks=jwks,
        client_id=client_id,
        nonce=nonce,
    )
