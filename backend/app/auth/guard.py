"""Who may call the API.

Installed as a dependency on the whole FastAPI application, so a route
added later is private by default; only the paths in PUBLIC are not.

Three ways in:

* the owner's browser: an HttpOnly session cookie, plus a CSRF token in
  a header on every request that changes something;
* the paired Chrome extension: a Bearer token that may only read the
  answer bank and the work and education history;
* nobody, when ACE_AUTH=disabled, but only from this computer or a
  private network (the rollback switch).
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)

from fastapi import (
    Depends,
    HTTPException,
    Request,
)
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.auth import service
from backend.app.auth.crypto import (
    digest,
    same,
)
from backend.app.config import get_settings
from backend.app.db.models import (
    ApiTokenRecord,
    AuthSessionRecord,
    UserRecord,
)


SESSION_COOKIE = "ace_session"

CSRF_COOKIE = "ace_csrf"

CSRF_HEADER = "x-csrf-token"

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Reachable signed out: signing in, and saying whether one is signed in.
PUBLIC = frozenset(
    {
        "/api/auth/status",
        "/api/auth/google/start",
        "/api/auth/google/callback",
        "/api/auth/login",
        "/api/auth/login/verify",
        "/api/auth/logout",
        "/api/auth/reset/request",
        "/api/auth/reset/confirm",
        "/api/extension/pair",
        "/api/auth/setup",
    }
)

# All the extension ever needs. Least privilege: a stolen extension
# token reads the answer bank and nothing else, and changes nothing.
EXTENSION_PATHS = frozenset(
    {
        "/api/answers",
        "/api/history/work",
        "/api/history/education",
        "/api/auth/status",
    }
)


@dataclass(frozen=True)
class Principal:
    kind: str  # session | token | local
    user: UserRecord | None = None
    auth_session: AuthSessionRecord | None = None
    token: ApiTokenRecord | None = None


def _ip(value: str) -> ipaddress._BaseAddress | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


# Named explicitly: Python's is_private also counts the documentation
# ranges and others that are not "this computer or my network".
LOCAL_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
    )
)


def _is_local(address: ipaddress._BaseAddress | None) -> bool:
    if address is None:
        return False
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    return any(
        address.version == net.version and address in net
        for net in LOCAL_NETWORKS
    )


def _forwarded(request: Request) -> list[str]:
    raw = request.headers.get("x-forwarded-for", "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def client_ip(request: Request) -> str:
    """The caller's address. A forwarded header is believed only when the
    direct peer is a local proxy (Next.js, Caddy), and then only its last
    entry, the one that proxy wrote itself."""

    peer = request.client.host if request.client else ""
    forwarded = _forwarded(request)

    if forwarded and _is_local(_ip(peer)):
        return forwarded[-1]

    return peer or "unknown"


def is_local_peer(request: Request) -> bool:
    """True when the application is reached through a trusted local proxy.

    Unlike ``is_local_request``, this deliberately ignores the original
    browser address in X-Forwarded-For. It is used only to decide whether a
    proxy's HTTPS signal is trustworthy, never to bypass authentication.
    """

    peer = request.client.host if request.client else ""
    return _is_local(_ip(peer))


def is_local_request(request: Request) -> bool:
    """True only when the peer and every forwarded hop are on this
    machine or a private network."""

    peer = request.client.host if request.client else ""

    if peer == "testclient":
        return False

    hops = [peer, *_forwarded(request)]
    return all(_is_local(_ip(hop)) for hop in hops)


def _refuse(status: int, reason: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"reason": reason, "message": message},
    )


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return None


def resolve(request: Request, session: Session) -> Principal | None:
    """Identify the caller without deciding whether the route allows it."""

    now = datetime.now(timezone.utc)
    bearer = _bearer(request)

    if bearer:
        found = service.token_for(session, bearer, now=now)
        if found is None:
            return None
        token, user = found
        return Principal(kind="token", user=user, token=token)

    cookie = request.cookies.get(SESSION_COOKIE, "")
    found = service.session_for(session, cookie, now=now)

    if found is None:
        return None

    row, user = found
    return Principal(kind="session", user=user, auth_session=row)


def require_auth(
    request: Request,
    session: Session = Depends(get_session),
) -> Principal | None:
    path = request.url.path

    if not path.startswith("/api/") or path in PUBLIC:
        return None

    settings = get_settings()

    if settings.ace_auth == "disabled":
        if is_local_request(request):
            principal = Principal(kind="local")
            request.state.principal = principal
            return principal

        raise _refuse(
            403,
            "auth_disabled_remote",
            "Sign-in is switched off, so ace answers only on this computer.",
        )

    principal = resolve(request, session)

    if principal is None:
        if _bearer(request):
            raise _refuse(
                401,
                "token_invalid",
                "This extension is no longer paired. Pair it again from Settings.",
            )
        raise _refuse(401, "signed_out", "Sign in to ace.")

    if principal.user is None or principal.user.role != service.OWNER:
        raise _refuse(403, "not_owner", "This account cannot read ace.")

    if principal.kind == "token":
        if request.method != "GET" or path not in EXTENSION_PATHS:
            raise _refuse(
                403,
                "scope",
                "The extension may only read answers and history.",
            )

    elif request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not sent or not same(digest(sent), principal.auth_session.csrf_hash):
            raise _refuse(
                403,
                "csrf",
                "This request did not come from an ace page. Reload and try again.",
            )

    request.state.principal = principal
    return principal


def current_owner(request: Request) -> UserRecord:
    """For routes that act on the account itself (sessions, pairing)."""

    principal: Principal | None = getattr(request.state, "principal", None)

    if principal is None or principal.kind != "session" or principal.user is None:
        raise _refuse(
            403,
            "session_required",
            "Sign in with a password to manage this. "
            "It is unavailable while sign-in is switched off.",
        )

    return principal.user
