"""Minimal read-only Gmail OAuth and API client.

No mailbox mutation endpoints are present. Access tokens are kept in memory
for one sync call; only the encrypted refresh token is persisted.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from backend.app.auth.google import DISCOVERY_URL, GoogleAuthError, verify_id_token

SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
API = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailError(ValueError):
    pass


class GmailCursorExpired(GmailError):
    pass


def configured(client_id: str, client_secret: str, redirect_uri: str, key: str) -> bool:
    try:
        Fernet(key.encode("ascii"))
    except (ValueError, UnicodeError):
        return False
    return bool(client_id and client_secret and redirect_uri.startswith("https://"))


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def authorization_url(client_id: str, redirect_uri: str, state: str, nonce: str, challenge: str) -> str:
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email " + SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })


def encrypt_token(token: str, key: str) -> bytes:
    return Fernet(key.encode("ascii")).encrypt(token.encode("utf-8"))


def decrypt_token(value: bytes, key: str) -> str:
    try:
        return Fernet(key.encode("ascii")).decrypt(value).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as error:
        raise GmailError("Stored Gmail authorization cannot be read.") from error


def exchange_code(code: str, verifier: str, nonce: str, *, client_id: str, client_secret: str, redirect_uri: str) -> tuple[str, str]:
    try:
        with httpx.Client(timeout=15) as client:
            discovery = client.get(DISCOVERY_URL)
            discovery.raise_for_status()
            endpoints = discovery.json()
            response = client.post(endpoints["token_endpoint"], data={
                "code": code, "code_verifier": verifier, "client_id": client_id,
                "client_secret": client_secret, "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
            response.raise_for_status()
            token = response.json()
            keys = client.get(endpoints["jwks_uri"])
            keys.raise_for_status()
        identity = verify_id_token(token["id_token"], jwks=keys.json(), client_id=client_id, nonce=nonce)
        refresh = token.get("refresh_token")
        scopes = set(str(token.get("scope", "")).split())
        if not isinstance(refresh, str) or not refresh or SCOPE not in scopes:
            raise GmailError("Gmail did not grant persistent read-only access.")
        return identity.email, refresh
    except (httpx.HTTPError, KeyError, TypeError, ValueError, GoogleAuthError) as error:
        if isinstance(error, GmailError):
            raise
        raise GmailError("Gmail connection could not be completed.") from error


def access_token(refresh: str, *, client_id: str, client_secret: str) -> str:
    try:
        response = httpx.post("https://oauth2.googleapis.com/token", data={
            "refresh_token": refresh, "client_id": client_id, "client_secret": client_secret,
            "grant_type": "refresh_token",
        }, timeout=15)
        response.raise_for_status()
        return str(response.json()["access_token"])
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        raise GmailError("Gmail authorization expired or could not be refreshed.") from error


def get_json(path: str, token: str, params: dict | None = None) -> dict:
    try:
        response = httpx.get(API + path, headers={"Authorization": "Bearer " + token}, params=params, timeout=20)
        if response.status_code == 404:
            raise GmailCursorExpired("Gmail history cursor expired.")
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError("invalid response")
        return value
    except (httpx.HTTPError, ValueError) as error:
        if isinstance(error, GmailError):
            raise
        raise GmailError("Gmail read could not be completed.") from error


def revoke(refresh: str) -> None:
    try:
        httpx.post("https://oauth2.googleapis.com/revoke", data={"token": refresh}, timeout=10)
    except httpx.HTTPError:
        pass  # The local grant is removed even if Google is unavailable.
