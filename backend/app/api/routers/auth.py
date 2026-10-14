"""Sign in, sign out, sessions, extension pairing and password reset.

The rules live in backend/app/auth/service.py; this file only turns
them into HTTP. Every refusal says what to do next, and none of them
reveals whether an email address has an account.
"""

from __future__ import annotations

import logging
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import get_session
from backend.app.auth import service
from backend.app.auth.crypto import (
    WeakPassword,
    verify_password,
)
from backend.app.auth.guard import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    client_ip,
    current_owner,
    is_local_request,
    resolve,
)
from backend.app.config import get_settings
from backend.app.db.models import UserRecord
from backend.app.mail.sender import (
    mail_configured,
    send,
)


LOGGER = logging.getLogger("ace.auth")

router = APIRouter()


class LoginRequest(BaseModel):
    email: str = ""
    password: str = ""


class PasswordChange(BaseModel):
    current_password: str = ""
    new_password: str = ""


class ResetRequest(BaseModel):
    email: str = ""


class ResetConfirm(BaseModel):
    token: str = ""
    new_password: str = ""


class PairRequest(BaseModel):
    code: str = ""
    name: str = ""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _refuse(status: int, reason: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"reason": reason, "message": message},
    )


def _json_only(request: Request) -> None:
    """A cross-site HTML form cannot send application/json without a CORS
    preflight, which ace never grants, so this closes login CSRF."""

    if not request.headers.get("content-type", "").startswith("application/json"):
        raise _refuse(415, "json_required", "Send JSON.")


def _secure(request: Request) -> bool:
    """Secure cookies whenever the browser is on HTTPS: directly, or
    through a proxy on this machine (Caddy) that says so."""

    if request.url.scheme == "https":
        return True

    return (
        request.headers.get("x-forwarded-proto", "") == "https"
        and is_local_request(request)
    )


def _set_cookies(
    response: Response,
    request: Request,
    *,
    token: str,
    csrf: str,
    max_age: int,
) -> None:
    secure = _secure(request)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    # Readable by the page on purpose: it copies it into a header, which
    # another site's page cannot do.
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=max_age,
        path="/",
        httponly=False,
        secure=secure,
        samesite="lax",
    )


def _clear_cookies(response: Response) -> None:
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/")


def _lifetime() -> timedelta:
    return timedelta(days=get_settings().session_days)


@router.get("/api/auth/status")
def status(
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    """Whether sign-in is on, an owner exists, and this caller is in."""

    settings = get_settings()
    principal = resolve(request, session)
    local = settings.ace_auth == "disabled" and is_local_request(request)

    return {
        "auth": settings.ace_auth,
        "owner_exists": service.owner_exists(session),
        "signed_in": bool(principal) or local,
        "kind": principal.kind if principal else ("local" if local else None),
        "email": (
            principal.user.email
            if principal and principal.user and principal.kind == "session"
            else None
        ),
        "reset_by_email": mail_configured(),
    }


@router.post("/api/auth/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> dict:
    _json_only(request)

    if not service.owner_exists(session):
        raise _refuse(
            409,
            "no_owner",
            "No owner account yet. Create it on the server with "
            "python -m backend.scripts.create_owner.",
        )

    try:
        created = service.login(
            session,
            email=payload.email,
            password=payload.password,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
            now=_now(),
            lifetime=_lifetime(),
        )
    except service.AuthRefused as refused:
        # The attempt is recorded even though the request fails.
        session.commit()
        LOGGER.info("login_refused reason=%s", refused.reason)
        raise _refuse(
            429 if refused.reason == "throttled" else 401,
            refused.reason,
            refused.message,
        ) from None

    session.commit()
    _set_cookies(
        response,
        request,
        token=created.token,
        csrf=created.csrf,
        max_age=int(_lifetime().total_seconds()),
    )
    LOGGER.info("login_ok user=%s", created.user.id)
    return {"ok": True, "email": created.user.email}


@router.post("/api/auth/logout")
def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> dict:
    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        service.logout(session, token, now=_now())
        session.commit()
    _clear_cookies(response)
    return {"ok": True}


@router.get("/api/auth/sessions")
def sessions(
    request: Request,
    session: Session = Depends(get_session),
    user: UserRecord = Depends(current_owner),
) -> dict:
    mine = request.state.principal.auth_session.token_hash
    return {
        "items": [
            {
                "id": row.id,
                "created_at": row.created_at.isoformat(),
                "last_seen_at": row.last_seen_at.isoformat(),
                "expires_at": row.expires_at.isoformat(),
                "user_agent": row.user_agent,
                "current": row.token_hash == mine,
            }
            for row in service.active_sessions(session, user, now=_now())
        ]
    }


@router.post("/api/auth/sessions/revoke-others")
def revoke_others(
    request: Request,
    session: Session = Depends(get_session),
    user: UserRecord = Depends(current_owner),
) -> dict:
    count = service.revoke_all_sessions(
        session,
        user,
        now=_now(),
        keep_token_hash=request.state.principal.auth_session.token_hash,
    )
    session.commit()
    return {"revoked": count}


@router.post("/api/auth/password")
def change_password(
    payload: PasswordChange,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    user: UserRecord = Depends(current_owner),
) -> dict:
    if not verify_password(user.password_hash, payload.current_password):
        raise _refuse(403, "invalid", "The current password is wrong.")

    try:
        service.set_password(session, user, payload.new_password, now=_now())
    except WeakPassword as weak:
        raise _refuse(400, "weak_password", str(weak)) from None

    # Every session was signed out, this one included; start a fresh one
    # so the person who just changed it stays in.
    created = service.start_session(
        session,
        user,
        user_agent=request.headers.get("user-agent", ""),
        now=_now(),
        lifetime=_lifetime(),
    )
    session.commit()
    _set_cookies(
        response,
        request,
        token=created.token,
        csrf=created.csrf,
        max_age=int(_lifetime().total_seconds()),
    )
    return {"ok": True}


@router.post("/api/auth/reset/request")
def reset_request(
    payload: ResetRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    """Always the same answer, so the endpoint does not reveal accounts."""

    _json_only(request)
    answer = {
        "ok": True,
        "message": "If that address has an account, a reset link is on its way.",
    }

    if not mail_configured():
        # A link that cannot be mailed is not created: logging it would
        # put a working credential in the log.
        return answer

    started = service.start_reset(
        session, email=payload.email, ip=client_ip(request), now=_now()
    )
    session.commit()

    if started is not None:
        user, token = started
        link = f"{get_settings().web_base_url.rstrip('/')}/login/reset?token={token}"
        send(
            to=user.email,
            subject="Reset your ace password",
            text=(
                "Someone asked to reset the password for ace.\n\n"
                f"Open this link within 30 minutes to choose a new one:\n{link}\n\n"
                "If it was not you, ignore this message; nothing has changed."
            ),
        )

    return answer


@router.post("/api/auth/reset/confirm")
def reset_confirm(
    payload: ResetConfirm,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    _json_only(request)
    try:
        service.finish_reset(
            session, token=payload.token, password=payload.new_password, now=_now()
        )
    except service.AuthRefused as refused:
        raise _refuse(400, refused.reason, refused.message) from None
    except WeakPassword as weak:
        raise _refuse(400, "weak_password", str(weak)) from None
    session.commit()
    return {"ok": True}


# ----------------------------------------------------------------------
# Extension pairing
# ----------------------------------------------------------------------


@router.post("/api/extension/pairing")
def start_pairing(
    session: Session = Depends(get_session),
    user: UserRecord = Depends(current_owner),
) -> dict:
    code = service.start_pairing(session, user, now=_now())
    session.commit()
    return {
        "code": f"{code[:4]} {code[4:]}",
        "expires_in_seconds": int(service.PAIRING_TTL.total_seconds()),
    }


@router.post("/api/extension/pair")
def pair(
    payload: PairRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    _json_only(request)
    try:
        token, record = service.redeem_pairing(
            session,
            code=payload.code,
            name=payload.name,
            ip=client_ip(request),
            now=_now(),
        )
    except service.AuthRefused as refused:
        session.commit()
        raise _refuse(
            429 if refused.reason == "throttled" else 400,
            refused.reason,
            refused.message,
        ) from None

    session.commit()
    LOGGER.info("extension_paired token=%s", record.prefix)
    return {"token": token, "name": record.name}


@router.get("/api/extension/tokens")
def tokens(
    session: Session = Depends(get_session),
    user: UserRecord = Depends(current_owner),
) -> dict:
    return {
        "items": [
            {
                "id": row.id,
                "name": row.name,
                "prefix": row.prefix,
                "created_at": row.created_at.isoformat(),
                "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
            }
            for row in service.list_tokens(session, user)
        ]
    }


@router.delete("/api/extension/tokens/{token_id}")
def revoke_token(
    token_id: int,
    session: Session = Depends(get_session),
    user: UserRecord = Depends(current_owner),
) -> dict:
    if not service.revoke_token(session, user, token_id, now=_now()):
        raise _refuse(404, "not_found", "No such paired device.")
    session.commit()
    return {"ok": True}
