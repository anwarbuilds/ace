"""Owner-only sign-in, extension pairing and the rollback switch.

Every private route must refuse an anonymous caller; the owner's browser
must get in with a cookie and a CSRF header; the extension must get in
with its token, and only to read answers and history. Fictional
addresses and passwords only.
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import (
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_session
from backend.app.api.main import create_app
from backend.app.auth import service
from backend.app.auth.crypto import (
    WeakPassword,
    hash_password,
    normalise_code,
)
from backend.app.auth.guard import (
    CSRF_COOKIE,
    EXTENSION_PATHS,
    PUBLIC,
    SESSION_COOKIE,
)
from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import (
    ApiTokenRecord,
    AuthSessionRecord,
    UserRecord,
)


EMAIL = "owner@example.com"

PASSWORD = "correct horse battery staple"

NOW = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)


@pytest.fixture(name="factory")
def fixture_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def _app(factory, monkeypatch, *, auth="required"):
    monkeypatch.setenv("ACE_AUTH", auth)
    monkeypatch.setenv("RESEND_API_KEY", "")
    get_settings.cache_clear()

    def override():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override
    return app


@pytest.fixture(name="client")
def fixture_client(factory, monkeypatch):
    with factory.begin() as session:
        service.create_owner(session, email=EMAIL, password=PASSWORD, now=NOW)
    yield TestClient(_app(factory, monkeypatch))
    get_settings.cache_clear()


def _login(client, email=EMAIL, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _csrf(client) -> dict:
    return {"X-CSRF-Token": client.cookies.get(CSRF_COOKIE)}


# ----------------------------------------------------------------------
# Anonymous callers
# ----------------------------------------------------------------------


def _private_routes(app):
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/") or route.path in PUBLIC:
            continue
        for method in route.methods:
            yield method, route.path.replace("{job_id}", "1").replace(
                "{kind}", "work"
            ).replace("{token_id}", "1")


def test_every_private_route_refuses_an_anonymous_caller(client) -> None:
    routes = list(_private_routes(client.app))
    assert len(routes) > 20

    for method, path in routes:
        response = client.request(method, path)
        assert response.status_code == 401, (method, path, response.text)
        assert response.json()["detail"]["reason"] == "signed_out"


def test_health_and_sign_in_stay_reachable(client) -> None:
    assert client.get("/healthz").status_code == 200

    status = client.get("/api/auth/status").json()
    assert status["auth"] == "required"
    assert status["owner_exists"] is True
    assert status["signed_in"] is False
    assert status["email"] is None


def test_api_docs_are_off_by_default(client) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_responses_carry_hardening_headers(client) -> None:
    headers = client.get("/healthz").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]


# ----------------------------------------------------------------------
# The owner's browser
# ----------------------------------------------------------------------


def test_the_owner_signs_in_and_reads(client) -> None:
    response = _login(client)
    assert response.status_code == 200

    cookie = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookie if c.startswith(SESSION_COOKIE + "="))
    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie
    csrf_cookie = next(c for c in cookie if c.startswith(CSRF_COOKIE + "="))
    assert "HttpOnly" not in csrf_cookie

    assert client.get("/api/answers").status_code == 200
    assert client.get("/api/auth/status").json()["email"] == EMAIL


def test_a_cookie_is_not_secure_on_plain_http_but_is_behind_https(client) -> None:
    plain = _login(client).headers.get_list("set-cookie")
    assert not any("Secure" in c for c in plain)

    https = TestClient(client.app, base_url="https://ace.example")
    secure = _login(https).headers.get_list("set-cookie")
    assert all("Secure" in c for c in secure)


def test_the_database_holds_no_usable_secret(client, factory) -> None:
    _login(client)
    token = client.cookies.get(SESSION_COOKIE)

    with factory() as session:
        user = session.scalar(select(UserRecord))
        row = session.scalar(select(AuthSessionRecord))

    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash
    assert row.token_hash != token and len(row.token_hash) == 64


def test_a_change_without_the_csrf_header_is_refused(client) -> None:
    _login(client)

    refused = client.put("/api/answers", json={"items": []})
    assert refused.status_code == 403
    assert refused.json()["detail"]["reason"] == "csrf"

    wrong = client.put(
        "/api/answers", json={"items": []}, headers={"X-CSRF-Token": "guess"}
    )
    assert wrong.status_code == 403

    allowed = client.put("/api/answers", json={"items": []}, headers=_csrf(client))
    assert allowed.status_code == 200


def test_another_sessions_csrf_token_does_not_work(client, factory, monkeypatch) -> None:
    other = TestClient(client.app)
    _login(other)
    _login(client)

    response = client.put(
        "/api/answers", json={"items": []}, headers=_csrf(other)
    )
    assert response.status_code == 403


def test_a_wrong_password_and_an_unknown_address_read_the_same(client) -> None:
    wrong = _login(client, password="not the password at all")
    unknown = _login(client, email="nobody@example.com")

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_login_needs_json(client) -> None:
    response = client.post(
        "/api/auth/login",
        content=f"email={EMAIL}&password=x",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code in (415, 422)


def test_repeated_failures_are_throttled_even_with_the_right_password(client) -> None:
    for _ in range(service.MAX_FAILURES_PER_EMAIL):
        assert _login(client, password="wrong password here").status_code == 401

    blocked = _login(client)
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["reason"] == "throttled"


def test_throttling_expires_after_the_window(factory) -> None:
    with factory.begin() as session:
        service.create_owner(session, email=EMAIL, password=PASSWORD, now=NOW)

    with factory.begin() as session:
        for _ in range(service.MAX_FAILURES_PER_EMAIL):
            with pytest.raises(service.AuthRefused):
                service.login(session, email=EMAIL, password="wrong one here",
                              ip="198.51.100.7", user_agent="", now=NOW,
                              lifetime=timedelta(days=1))

    later = NOW + service.WINDOW + timedelta(seconds=1)
    with factory.begin() as session:
        created = service.login(session, email=EMAIL, password=PASSWORD,
                                ip="198.51.100.7", user_agent="", now=later,
                                lifetime=timedelta(days=1))
    assert created.token


def test_logout_ends_the_session_on_the_server(client) -> None:
    _login(client)
    token = client.cookies.get(SESSION_COOKIE)

    assert client.post("/api/auth/logout").status_code == 200

    replay = TestClient(client.app)
    replay.cookies.set(SESSION_COOKIE, token)
    assert replay.get("/api/answers").status_code == 401


def test_an_expired_session_is_refused(factory) -> None:
    with factory.begin() as session:
        user = service.create_owner(session, email=EMAIL, password=PASSWORD, now=NOW)
        created = service.start_session(session, user, user_agent="", now=NOW,
                                        lifetime=timedelta(days=30))

    with factory() as session:
        assert service.session_for(session, created.token, now=NOW + timedelta(days=29))
        assert service.session_for(session, created.token, now=NOW + timedelta(days=31)) is None


def test_revoking_other_sessions_keeps_this_one(client) -> None:
    other = TestClient(client.app)
    _login(other)
    _login(client)

    listed = client.get("/api/auth/sessions").json()["items"]
    assert len(listed) == 2
    assert sum(1 for row in listed if row["current"]) == 1

    revoked = client.post("/api/auth/sessions/revoke-others", headers=_csrf(client))
    assert revoked.json() == {"revoked": 1}
    assert client.get("/api/answers").status_code == 200
    assert other.get("/api/answers").status_code == 401


def test_changing_the_password_signs_other_browsers_out(client) -> None:
    other = TestClient(client.app)
    _login(other)
    _login(client)

    weak = client.post("/api/auth/password", headers=_csrf(client),
                       json={"current_password": PASSWORD, "new_password": "short"})
    assert weak.status_code == 400

    wrong = client.post("/api/auth/password", headers=_csrf(client),
                        json={"current_password": "nope nope nope", "new_password": "a much longer passphrase"})
    assert wrong.status_code == 403

    ok = client.post("/api/auth/password", headers=_csrf(client),
                     json={"current_password": PASSWORD, "new_password": "a much longer passphrase"})
    assert ok.status_code == 200
    assert client.get("/api/answers").status_code == 200
    assert other.get("/api/answers").status_code == 401
    assert _login(TestClient(client.app), password="a much longer passphrase").status_code == 200


def test_a_non_owner_account_is_refused(factory, monkeypatch) -> None:
    with factory.begin() as session:
        session.add(UserRecord(email="guest@example.com", password_hash=hash_password(PASSWORD),
                               role="viewer", is_active=True, created_at=NOW,
                               password_changed_at=NOW))
        service.create_owner(session, email=EMAIL, password=PASSWORD, now=NOW)

    client = TestClient(_app(factory, monkeypatch))
    assert _login(client, email="guest@example.com").status_code == 200
    response = client.get("/api/answers")
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "not_owner"
    get_settings.cache_clear()


def test_with_no_owner_login_says_how_to_create_one(factory, monkeypatch) -> None:
    client = TestClient(_app(factory, monkeypatch))
    response = _login(client)
    assert response.status_code == 409
    assert "create_owner" in response.json()["detail"]["message"]
    assert client.get("/api/auth/status").json()["owner_exists"] is False
    get_settings.cache_clear()


# ----------------------------------------------------------------------
# The owner account
# ----------------------------------------------------------------------


def test_there_is_only_ever_one_owner(factory) -> None:
    with factory.begin() as session:
        service.create_owner(session, email=EMAIL, password=PASSWORD, now=NOW)

    with factory.begin() as session, pytest.raises(service.AuthRefused):
        service.create_owner(session, email="second@example.com", password=PASSWORD, now=NOW)


@pytest.mark.parametrize("password", ["short", "x" * 11, EMAIL, "y" * 257])
def test_the_password_policy(factory, password) -> None:
    with factory.begin() as session, pytest.raises(WeakPassword):
        service.create_owner(session, email=EMAIL, password=password, now=NOW)


def test_dead_sessions_are_pruned_on_sign_in(factory) -> None:
    with factory.begin() as session:
        user = service.create_owner(session, email=EMAIL, password=PASSWORD, now=NOW)
        old = service.start_session(session, user, user_agent="", now=NOW, lifetime=timedelta(days=1))
        service.logout(session, old.token, now=NOW)

    later = NOW + service.DEAD_SESSION_RETENTION + timedelta(days=2)
    with factory.begin() as session:
        service.start_session(session, user, user_agent="", now=later, lifetime=timedelta(days=1))
        assert session.scalar(select(func.count(AuthSessionRecord.id))) == 1


def test_email_is_case_insensitive(client) -> None:
    assert _login(client, email="  Owner@Example.COM ").status_code == 200


# ----------------------------------------------------------------------
# The extension
# ----------------------------------------------------------------------


def _pair(client) -> str:
    _login(client)
    code = client.post("/api/extension/pairing", headers=_csrf(client)).json()["code"]
    extension = TestClient(client.app)
    response = extension.post("/api/extension/pair", json={"code": code.lower(), "name": "Chrome"})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def test_the_extension_pairs_and_reads_answers_and_history(client) -> None:
    token = _pair(client)
    extension = TestClient(client.app)
    bearer = {"Authorization": f"Bearer {token}"}

    for path in ("/api/answers", "/api/history/work", "/api/history/education"):
        assert extension.get(path, headers=bearer).status_code == 200, path

    assert extension.get("/api/auth/status", headers=bearer).json()["kind"] == "token"


def test_the_extension_token_reads_nothing_else_and_changes_nothing(client) -> None:
    token = _pair(client)
    extension = TestClient(client.app)
    bearer = {"Authorization": f"Bearer {token}"}

    assert extension.get("/api/jobs", headers=bearer).status_code == 403
    assert extension.get("/api/export.json", headers=bearer).status_code == 403
    assert extension.put("/api/answers", json={"items": []}, headers=bearer).status_code == 403
    assert extension.get("/api/extension/tokens", headers=bearer).status_code == 403


def test_the_extension_scope_is_read_only_by_construction() -> None:
    assert EXTENSION_PATHS == {
        "/api/answers", "/api/history/work", "/api/history/education", "/api/auth/status"
    }


def test_a_pairing_code_works_once(client) -> None:
    _login(client)
    code = client.post("/api/extension/pairing", headers=_csrf(client)).json()["code"]
    extension = TestClient(client.app)
    assert extension.post("/api/extension/pair", json={"code": code}).status_code == 200
    again = extension.post("/api/extension/pair", json={"code": code})
    assert again.status_code == 400
    assert again.json()["detail"]["reason"] == "invalid_code"


def test_a_new_pairing_code_cancels_the_old_one(client) -> None:
    _login(client)
    first = client.post("/api/extension/pairing", headers=_csrf(client)).json()["code"]
    client.post("/api/extension/pairing", headers=_csrf(client))
    extension = TestClient(client.app)
    assert extension.post("/api/extension/pair", json={"code": first}).status_code == 400


def test_a_pairing_code_expires(factory) -> None:
    with factory.begin() as session:
        user = service.create_owner(session, email=EMAIL, password=PASSWORD, now=NOW)
        code = service.start_pairing(session, user, now=NOW)

    with factory.begin() as session, pytest.raises(service.AuthRefused):
        service.redeem_pairing(session, code=code, name="", ip="203.0.113.9",
                               now=NOW + service.PAIRING_TTL + timedelta(seconds=1))


def test_pairing_guesses_are_throttled(client) -> None:
    extension = TestClient(client.app)
    for _ in range(service.MAX_PAIRING_FAILURES_PER_IP):
        assert extension.post("/api/extension/pair", json={"code": "AAAA AAAA"}).status_code == 400
    assert extension.post("/api/extension/pair", json={"code": "AAAA AAAA"}).status_code == 429


def test_a_revoked_token_stops_working_at_once(client) -> None:
    token = _pair(client)
    listed = client.get("/api/extension/tokens").json()["items"]
    assert len(listed) == 1 and token.startswith(listed[0]["prefix"])
    assert token not in str(listed)

    assert client.delete(f"/api/extension/tokens/{listed[0]['id']}", headers=_csrf(client)).status_code == 200

    response = TestClient(client.app).get(
        "/api/answers", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"]["reason"] == "token_invalid"


def test_the_token_survives_a_password_change(client, factory) -> None:
    token = _pair(client)
    client.post("/api/auth/password", headers=_csrf(client),
                json={"current_password": PASSWORD, "new_password": "a much longer passphrase"})
    response = TestClient(client.app).get(
        "/api/answers", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


def test_pairing_needs_a_password_session(client) -> None:
    token = _pair(client)
    extension = TestClient(client.app)
    response = extension.post("/api/extension/pairing",
                              headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_codes_are_typed_forgivingly() -> None:
    assert normalise_code(" abcd efgh ") == "ABCDEFGH"


# ----------------------------------------------------------------------
# Password reset
# ----------------------------------------------------------------------


def test_reset_without_a_mail_provider_creates_nothing(client, factory) -> None:
    response = client.post("/api/auth/reset/request", json={"email": EMAIL})
    assert response.status_code == 200

    with factory() as session:
        from backend.app.db.models import AuthCodeRecord
        assert session.scalar(select(AuthCodeRecord)) is None


def test_reset_answers_the_same_for_any_address(client, monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test-key-not-real")
    get_settings.cache_clear()
    sent = []
    monkeypatch.setattr("backend.app.api.routers.auth.send", lambda **kw: sent.append(kw) or True)

    known = client.post("/api/auth/reset/request", json={"email": EMAIL})
    unknown = client.post("/api/auth/reset/request", json={"email": "nobody@example.com"})

    assert known.json() == unknown.json()
    assert len(sent) == 1 and sent[0]["to"] == EMAIL
    assert "/login/reset?token=" in sent[0]["text"]


def test_a_reset_link_sets_the_password_once(factory) -> None:
    with factory.begin() as session:
        service.create_owner(session, email=EMAIL, password=PASSWORD, now=NOW)
        user, token = service.start_reset(session, email=EMAIL, ip="203.0.113.9", now=NOW)
        service.start_session(session, user, user_agent="", now=NOW, lifetime=timedelta(days=1))

    with factory.begin() as session:
        service.finish_reset(session, token=token, password="a brand new passphrase", now=NOW)
        assert service.active_sessions(session, user, now=NOW) == []

    with factory.begin() as session, pytest.raises(service.AuthRefused):
        service.finish_reset(session, token=token, password="another new passphrase", now=NOW)


def test_a_reset_link_expires(factory) -> None:
    with factory.begin() as session:
        service.create_owner(session, email=EMAIL, password=PASSWORD, now=NOW)
        _, token = service.start_reset(session, email=EMAIL, ip="203.0.113.9", now=NOW)

    with factory.begin() as session, pytest.raises(service.AuthRefused):
        service.finish_reset(session, token=token, password="a brand new passphrase",
                             now=NOW + service.RESET_TTL + timedelta(seconds=1))


# ----------------------------------------------------------------------
# The rollback switch
# ----------------------------------------------------------------------


class _Peer:
    """Run requests as if from a given address."""

    def __init__(self, app, host):
        self.client = TestClient(app, client=(host, 50000))


def test_disabled_auth_answers_this_computer(factory, monkeypatch) -> None:
    app = _app(factory, monkeypatch, auth="disabled")
    local = _Peer(app, "127.0.0.1").client
    assert local.get("/api/answers").status_code == 200
    assert local.put("/api/answers", json={"items": []}).status_code == 200
    assert local.get("/api/auth/status").json()["kind"] == "local"
    get_settings.cache_clear()


def test_disabled_auth_never_answers_a_public_address(factory, monkeypatch) -> None:
    app = _app(factory, monkeypatch, auth="disabled")

    remote = _Peer(app, "203.0.113.5").client
    assert remote.get("/api/answers").status_code == 403

    # A local proxy forwarding a public caller is a public caller.
    proxied = _Peer(app, "127.0.0.1").client
    response = proxied.get("/api/answers", headers={"X-Forwarded-For": "198.51.100.20"})
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "auth_disabled_remote"
    get_settings.cache_clear()


def test_account_routes_need_a_real_session_even_when_disabled(factory, monkeypatch) -> None:
    app = _app(factory, monkeypatch, auth="disabled")
    local = _Peer(app, "127.0.0.1").client
    assert local.post("/api/extension/pairing").status_code == 403
    get_settings.cache_clear()


def test_a_typo_in_the_switch_is_refused(monkeypatch) -> None:
    monkeypatch.setenv("ACE_AUTH", "off")
    get_settings.cache_clear()
    with pytest.raises(Exception):
        get_settings()
    get_settings.cache_clear()


def test_the_cli_creates_the_owner_from_a_hidden_prompt(factory, monkeypatch, capsys) -> None:
    import backend.app.db.session as db_session
    from backend.scripts import create_owner

    monkeypatch.setattr(db_session, "SessionLocal", factory)
    monkeypatch.setattr(create_owner.getpass, "getpass", lambda prompt="": PASSWORD)

    assert create_owner.main([EMAIL]) == 0
    assert "Owner created" in capsys.readouterr().out

    with pytest.raises(SystemExit):
        create_owner.main(["second@example.com"])

    monkeypatch.setattr(create_owner.getpass, "getpass", lambda prompt="": "a new long passphrase")
    assert create_owner.main([EMAIL, "--reset"]) == 0

    with factory() as session:
        user = service.find_user(session, EMAIL)
        from backend.app.auth.crypto import verify_password
        assert verify_password(user.password_hash, "a new long passphrase")


def test_the_cli_refuses_mismatched_passwords(factory, monkeypatch) -> None:
    import backend.app.db.session as db_session
    from backend.scripts import create_owner

    answers = iter(["first long passphrase", "second long passphrase"])
    monkeypatch.setattr(db_session, "SessionLocal", factory)
    monkeypatch.setattr(create_owner.getpass, "getpass", lambda prompt="": next(answers))

    with pytest.raises(SystemExit):
        create_owner.main([EMAIL])

    with factory() as session:
        assert service.owner_exists(session) is False
