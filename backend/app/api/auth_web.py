"""The login surface, and the wall in front of everything else.

Authentication is enforced by middleware over an allowlist rather than
by a dependency on each route. There are 21 routes and adding the 22nd
without its dependency would expose it silently, so the default has to
be "protected" and the exceptions have to be written down in one place.

Fail closed, not open.
"""

from __future__ import annotations

from fastapi import (
    FastAPI,
    Form,
    Request,
)
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)

from backend.app.auth.service import (
    ABSOLUTE_LIFETIME,
    authenticate,
    end_session,
    resolve_session,
    start_session,
)
from backend.app.config import get_settings
from backend.app.db.session import SessionLocal


SESSION_COOKIE = "ace_session"


# Everything reachable without signing in. Deliberately short, and
# deliberately explicit: a prefix like "/api" would be a hole.
PUBLIC_PATHS = frozenset(
    {
        "/healthz",
        "/login",
        "/logout",
    }
)

PUBLIC_PREFIXES = (
    # The login page's own stylesheet and favicon.
    "/static/login",
)


LOGIN_PAGE = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ACE</title>
<style>
  :root{color-scheme:dark}
  body{margin:0;min-height:100vh;display:flex;align-items:center;
    justify-content:center;background:#0f0a17;color:#f4f0fa;
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
  form{width:min(360px,90vw);background:#1c1229;border:1px solid #33244a;
    border-radius:14px;padding:28px}
  h1{margin:0 0 4px;font-size:19px;letter-spacing:.14em}
  p{margin:0 0 22px;font-size:12px;color:#b3a3cd}
  label{display:block;font-size:11px;letter-spacing:.06em;
    text-transform:uppercase;color:#b3a3cd;margin:14px 0 6px}
  input{width:100%;box-sizing:border-box;padding:10px 12px;border-radius:8px;
    border:1px solid #4a3468;background:#150e20;color:#f4f0fa;font-size:14px;
    font-family:inherit}
  input:focus{outline:2px solid #8b6fc7;outline-offset:1px}
  button{width:100%;margin-top:20px;padding:11px;border:0;border-radius:8px;
    background:#c9a227;color:#231633;font-weight:600;font-size:14px;
    cursor:pointer;font-family:inherit}
  button:hover{background:#dcb534}
  .err{margin-top:16px;padding:9px 12px;border-radius:8px;
    background:#3a1720;border:1px solid #7d2b3a;color:#ffb4c0;font-size:12.5px}
</style>
<form method="post" action="/login">
  <h1>ACE</h1>
  <p>Automated Career Engine</p>
  <label for="email">Email</label>
  <input id="email" name="email" type="email" autocomplete="username"
         required autofocus>
  <label for="password">Password</label>
  <input id="password" name="password" type="password"
         autocomplete="current-password" required>
  <button type="submit">Sign in</button>
  __ERROR__
</form>
"""


def _is_public(
    path: str,
) -> bool:
    """Whether a path may be reached without signing in."""

    if path in PUBLIC_PATHS:
        return True

    return any(
        path.startswith(
            prefix,
        )
        for prefix in PUBLIC_PREFIXES
    )


def _render_login(
    error: str = "",
) -> HTMLResponse:
    block = (
        f'<div class="err">{error}</div>'
        if error
        else ""
    )

    return HTMLResponse(
        LOGIN_PAGE.replace(
            "__ERROR__",
            block,
        ),
        # A failed attempt must not be cached, and neither must the
        # form, or a back button can serve it after signing out.
        headers={
            "Cache-Control": (
                "no-store"
            ),
        },
        status_code=200 if not error else 401,
    )


def install(
    app: FastAPI,
) -> None:
    """Put the wall up, and add the doors through it."""

    settings = get_settings()

    @app.middleware("http")
    async def require_sign_in(
        request: Request,
        call_next,
    ):
        if not settings.require_authentication:
            return await call_next(
                request,
            )

        path = request.url.path

        if _is_public(
            path,
        ):
            return await call_next(
                request,
            )

        token = request.cookies.get(
            SESSION_COOKIE,
        )

        with SessionLocal() as session:
            user = resolve_session(
                session,
                token,
            )

            session.commit()

        if user is None:
            # An API caller gets an answer it can act on; a browser
            # gets the login page. Returning HTML to fetch() would
            # render as a parse error rather than "you are signed out".
            if path.startswith(
                "/api/"
            ):
                return JSONResponse(
                    {
                        "detail": (
                            "Not signed in."
                        ),
                    },
                    status_code=401,
                    headers={
                        "Cache-Control": (
                            "no-store"
                        ),
                    },
                )

            return RedirectResponse(
                "/login",
                status_code=303,
            )

        request.state.user_id = user.id

        return await call_next(
            request,
        )

    @app.get(
        "/login",
    )
    def login_form() -> HTMLResponse:
        """Show the sign-in page."""

        return _render_login()

    @app.post(
        "/login",
    )
    def login_submit(
        email: str = Form(...),
        password: str = Form(...),
    ) -> Response:
        """Check credentials and open a session."""

        with SessionLocal() as session:
            user = authenticate(
                session,
                email,
                password,
            )

            if user is None:
                # One message for both causes. Saying which was wrong
                # tells an attacker whether the address is registered.
                return _render_login(
                    "Email or password is "
                    "incorrect.",
                )

            token = start_session(
                session,
                user,
            )

            session.commit()

        response = RedirectResponse(
            "/",
            status_code=303,
        )

        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=int(
                ABSOLUTE_LIFETIME.total_seconds(),
            ),
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite="lax",
            path="/",
        )

        return response

    @app.get(
        "/logout",
    )
    def logout(
        request: Request,
    ) -> Response:
        """End this session and clear the cookie."""

        with SessionLocal() as session:
            end_session(
                session,
                request.cookies.get(
                    SESSION_COOKIE,
                ),
            )

            session.commit()

        response = RedirectResponse(
            "/login",
            status_code=303,
        )

        response.delete_cookie(
            SESSION_COOKIE,
            path="/",
        )

        return response
