"""Sign-in, sessions, extension pairing and password reset.

Pure functions over a SQLAlchemy session and an explicit `now`, so every
rule here is tested without a clock or a web server. The HTTP layer is
backend/app/api/routers/auth.py; enforcement is backend/app/auth/guard.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
)

from sqlalchemy import (
    delete,
    func,
    select,
    update,
)
from sqlalchemy.orm import Session

from backend.app.auth.crypto import (
    check_password_policy,
    digest,
    hash_password,
    needs_rehash,
    new_code,
    new_token,
    normalise_code,
    verify_password,
)
from backend.app.db.models import (
    ApiTokenRecord,
    AuthCodeRecord,
    AuthSessionRecord,
    LoginAttemptRecord,
    UserRecord,
)


OWNER = "owner"

EXTENSION_SCOPE = "extension"

EXTENSION_PREFIX = "ace_ext_"

# Guessing limits. Five wrong passwords for one address, or twenty from
# one network address, within the window, and further attempts are
# refused without checking the password until the window has passed.
WINDOW = timedelta(minutes=15)

MAX_FAILURES_PER_EMAIL = 5

MAX_FAILURES_PER_IP = 20

# Pairing codes are shorter than passwords, so they get fewer tries.
MAX_PAIRING_FAILURES_PER_IP = 10

PAIRING_TTL = timedelta(minutes=10)

LOGIN_CODE_TTL = timedelta(minutes=10)

RESET_TTL = timedelta(minutes=10)

MAX_CODE_FAILURES_PER_EMAIL = 5

MAX_CODE_FAILURES_PER_IP = 20

MAX_CODE_SENDS_PER_WINDOW = 5

# last_seen_at is written at most this often, so reading a page does not
# turn every request into a database write.
TOUCH_EVERY = timedelta(minutes=5)

# Attempt rows older than this are deleted when new ones are written.
ATTEMPT_RETENTION = timedelta(days=7)

# Expired or signed-out sessions are kept this long (for the record),
# then deleted when the next session starts.
DEAD_SESSION_RETENTION = timedelta(days=30)


class AuthRefused(Exception):
    """A request the auth layer turns down; `reason` is a stable code."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class NewSession:
    user: UserRecord
    token: str
    csrf: str
    expires_at: datetime


def _email(value: str) -> str:
    return value.strip().lower()


def find_user(session: Session, email: str) -> UserRecord | None:
    return session.scalar(
        select(UserRecord).where(UserRecord.email == _email(email))
    )


def owner_exists(session: Session) -> bool:
    return bool(
        session.scalar(
            select(func.count(UserRecord.id)).where(
                UserRecord.role == OWNER,
                UserRecord.is_active.is_(True),
            )
        )
    )


# ----------------------------------------------------------------------
# The owner
# ----------------------------------------------------------------------


def create_owner(
    session: Session,
    *,
    email: str,
    password: str,
    now: datetime,
) -> UserRecord:
    """Create the one owner. Refused if an owner already exists: there is
    no second account to create, and no open sign-up."""

    email = _email(email)

    if "@" not in email or len(email) > 320:
        raise AuthRefused("invalid_email", "Enter a valid email address.")

    if owner_exists(session) or find_user(session, email):
        raise AuthRefused(
            "owner_exists",
            "An owner already exists. Run this again with --reset to set a new password.",
        )

    check_password_policy(password, email=email)

    user = UserRecord(
        email=email,
        password_hash=hash_password(password),
        role=OWNER,
        is_active=True,
        created_at=now,
        password_changed_at=now,
    )
    session.add(user)
    session.flush()
    return user


def set_password(
    session: Session,
    user: UserRecord,
    password: str,
    *,
    now: datetime,
) -> None:
    """Change the password and sign every browser out. Extension tokens
    stay: they are separate credentials, revoked separately."""

    check_password_policy(password, email=user.email)
    user.password_hash = hash_password(password)
    user.password_changed_at = now
    revoke_all_sessions(session, user, now=now)


def set_owner_email(
    session: Session,
    user: UserRecord,
    email: str,
    *,
    now: datetime,
) -> None:
    """Move the single owner login to a new verified email address.

    Existing product data belongs to the database, not the email string, so
    it stays in place. Browser sessions and pending email codes are revoked,
    and a previous Google subject is cleared so the new address can bind on
    its first verified Google sign-in.
    """

    email = _email(email)
    if "@" not in email or len(email) > 320:
        raise AuthRefused("invalid_email", "Enter a valid email address.")
    if user.role != OWNER or not user.is_active:
        raise AuthRefused("not_owner", "The active owner account was not found.")

    existing = find_user(session, email)
    if existing is not None and existing.id != user.id:
        raise AuthRefused(
            "email_exists",
            "That email address already belongs to another account.",
        )

    if user.email == email:
        return

    user.email = email
    user.google_subject = None
    revoke_all_sessions(session, user, now=now)
    session.execute(
        update(AuthCodeRecord)
        .where(
            AuthCodeRecord.user_id == user.id,
            AuthCodeRecord.used_at.is_(None),
        )
        .values(used_at=now)
    )


# ----------------------------------------------------------------------
# Throttling
# ----------------------------------------------------------------------


def _failures(session: Session, key: str, now: datetime) -> int:
    return session.scalar(
        select(func.count(LoginAttemptRecord.id)).where(
            LoginAttemptRecord.key == key,
            LoginAttemptRecord.succeeded.is_(False),
            LoginAttemptRecord.attempted_at > now - WINDOW,
        )
    ) or 0


def _record(session: Session, keys: list[str], ok: bool, now: datetime) -> None:
    session.add_all(
        LoginAttemptRecord(key=key[:400], succeeded=ok, attempted_at=now)
        for key in keys
    )
    session.execute(
        delete(LoginAttemptRecord).where(
            LoginAttemptRecord.attempted_at < now - ATTEMPT_RETENTION
        )
    )


def _clear(session: Session, key: str) -> None:
    """A successful sign-in forgives earlier typos for that address."""

    session.execute(
        delete(LoginAttemptRecord).where(
            LoginAttemptRecord.key == key,
            LoginAttemptRecord.succeeded.is_(False),
        )
    )


# ----------------------------------------------------------------------
# Browser sessions
# ----------------------------------------------------------------------


def verify_login_password(
    session: Session,
    *,
    email: str,
    password: str,
    ip: str,
    now: datetime,
) -> UserRecord:
    email_key = "email:" + _email(email)
    ip_key = "ip:" + ip

    if (
        _failures(session, email_key, now) >= MAX_FAILURES_PER_EMAIL
        or _failures(session, ip_key, now) >= MAX_FAILURES_PER_IP
    ):
        _record(session, [ip_key], False, now)
        raise AuthRefused(
            "throttled",
            "Too many attempts. Wait 15 minutes, then try again.",
        )

    user = find_user(session, email)
    ok = verify_password(user.password_hash if user else None, password)

    if not ok or user is None or not user.is_active:
        _record(session, [email_key, ip_key], False, now)
        raise AuthRefused("invalid", "That email and password do not match.")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    _clear(session, email_key)
    _record(session, [email_key], True, now)
    return user


def login(
    session: Session,
    *,
    email: str,
    password: str,
    ip: str,
    user_agent: str,
    now: datetime,
    lifetime: timedelta,
) -> NewSession:
    """Complete password-only login when email delivery is disabled.

    Production HTTP login uses ``verify_login_password`` followed by a
    one-time email code. This wrapper preserves local development and the
    service API without creating a second authentication system.
    """

    user = verify_login_password(
        session,
        email=email,
        password=password,
        ip=ip,
        now=now,
    )
    return start_session(
        session, user, user_agent=user_agent, now=now, lifetime=lifetime
    )


def start_login_verification(
    session: Session,
    user: UserRecord,
    *,
    now: datetime,
) -> str:
    """Create the only live email code for a verified password login."""

    send_key = f"login-code-send:{user.id}"
    if _failures(session, send_key, now) >= MAX_CODE_SENDS_PER_WINDOW:
        raise AuthRefused(
            "throttled",
            "Too many verification codes were requested. Wait 15 minutes, then try again.",
        )

    _record(session, [send_key], False, now)
    session.execute(
        update(AuthCodeRecord)
        .where(
            AuthCodeRecord.user_id == user.id,
            AuthCodeRecord.purpose == "login_verification",
            AuthCodeRecord.used_at.is_(None),
        )
        .values(used_at=now)
    )
    code = new_code()
    session.add(
        AuthCodeRecord(
            code_hash=digest("login:" + code),
            purpose="login_verification",
            user_id=user.id,
            created_at=now,
            expires_at=now + LOGIN_CODE_TTL,
        )
    )
    session.flush()
    return code


def finish_login_verification(
    session: Session,
    *,
    email: str,
    code: str,
    ip: str,
    user_agent: str,
    now: datetime,
    lifetime: timedelta,
) -> NewSession:
    """Consume an email code and create the browser session once."""

    normal_email = _email(email)
    email_key = "login-code-email:" + normal_email
    ip_key = "login-code-ip:" + ip
    if (
        _failures(session, email_key, now) >= MAX_CODE_FAILURES_PER_EMAIL
        or _failures(session, ip_key, now) >= MAX_CODE_FAILURES_PER_IP
    ):
        _record(session, [ip_key], False, now)
        raise AuthRefused(
            "throttled",
            "Too many attempts. Wait 15 minutes, then try again.",
        )

    user = find_user(session, normal_email)
    row = session.scalar(
        select(AuthCodeRecord).where(
            AuthCodeRecord.code_hash
            == digest("login:" + normalise_code(code)),
            AuthCodeRecord.purpose == "login_verification",
        )
    )
    if (
        user is None
        or not user.is_active
        or row is None
        or row.user_id != user.id
        or row.used_at is not None
        or _aware(row.expires_at, now) <= now
    ):
        _record(session, [email_key, ip_key], False, now)
        raise AuthRefused(
            "invalid_code",
            "That verification code is invalid or expired. Request a new code.",
        )

    row.used_at = now
    _clear(session, email_key)
    _record(session, [email_key], True, now)
    return start_session(
        session,
        user,
        user_agent=user_agent,
        now=now,
        lifetime=lifetime,
    )


def start_session(
    session: Session,
    user: UserRecord,
    *,
    user_agent: str,
    now: datetime,
    lifetime: timedelta,
) -> NewSession:
    cutoff = now - DEAD_SESSION_RETENTION
    session.execute(
        delete(AuthSessionRecord).where(
            (AuthSessionRecord.expires_at < cutoff)
            | (AuthSessionRecord.revoked_at < cutoff)
        ),
        # Evaluated in SQL only: Python cannot compare SQLite's naive
        # timestamps with an aware cutoff, and no loaded row needs it.
        execution_options={"synchronize_session": False},
    )

    token = new_token()
    csrf = new_token()
    expires = now + lifetime
    session.add(
        AuthSessionRecord(
            token_hash=digest(token),
            csrf_hash=digest(csrf),
            user_id=user.id,
            created_at=now,
            last_seen_at=now,
            expires_at=expires,
            user_agent=(user_agent or "")[:200],
        )
    )
    session.flush()
    return NewSession(user=user, token=token, csrf=csrf, expires_at=expires)


def _aware(value: datetime, like: datetime) -> datetime:
    """SQLite hands back naive datetimes; compare them as UTC."""

    if value.tzinfo is None and like.tzinfo is not None:
        return value.replace(tzinfo=like.tzinfo)
    return value


def session_for(
    session: Session,
    token: str,
    *,
    now: datetime,
) -> tuple[AuthSessionRecord, UserRecord] | None:
    if not token:
        return None

    row = session.scalar(
        select(AuthSessionRecord).where(
            AuthSessionRecord.token_hash == digest(token)
        )
    )

    if row is None or row.revoked_at is not None:
        return None

    if _aware(row.expires_at, now) <= now:
        return None

    user = session.get(UserRecord, row.user_id)

    if user is None or not user.is_active:
        return None

    if now - _aware(row.last_seen_at, now) >= TOUCH_EVERY:
        row.last_seen_at = now
        session.commit()

    return row, user


def logout(session: Session, token: str, *, now: datetime) -> None:
    session.execute(
        update(AuthSessionRecord)
        .where(
            AuthSessionRecord.token_hash == digest(token),
            AuthSessionRecord.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )


def revoke_all_sessions(
    session: Session,
    user: UserRecord,
    *,
    now: datetime,
    keep_token_hash: str | None = None,
) -> int:
    statement = (
        update(AuthSessionRecord)
        .where(
            AuthSessionRecord.user_id == user.id,
            AuthSessionRecord.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    if keep_token_hash:
        statement = statement.where(
            AuthSessionRecord.token_hash != keep_token_hash
        )

    return session.execute(statement).rowcount or 0


def active_sessions(
    session: Session, user: UserRecord, *, now: datetime
) -> list[AuthSessionRecord]:
    rows = session.scalars(
        select(AuthSessionRecord)
        .where(
            AuthSessionRecord.user_id == user.id,
            AuthSessionRecord.revoked_at.is_(None),
        )
        .order_by(AuthSessionRecord.last_seen_at.desc())
    ).all()
    return [r for r in rows if _aware(r.expires_at, now) > now]


# ----------------------------------------------------------------------
# Extension pairing
# ----------------------------------------------------------------------


def start_pairing(session: Session, user: UserRecord, *, now: datetime) -> str:
    """A one-time code the owner types into the extension. Any earlier
    unused code is cancelled, so at most one is ever live."""

    session.execute(
        update(AuthCodeRecord)
        .where(
            AuthCodeRecord.user_id == user.id,
            AuthCodeRecord.purpose == "pairing",
            AuthCodeRecord.used_at.is_(None),
        )
        .values(used_at=now)
    )
    code = new_code()
    session.add(
        AuthCodeRecord(
            code_hash=digest("pairing:" + code),
            purpose="pairing",
            user_id=user.id,
            created_at=now,
            expires_at=now + PAIRING_TTL,
        )
    )
    session.flush()
    return code


def redeem_pairing(
    session: Session,
    *,
    code: str,
    name: str,
    ip: str,
    now: datetime,
) -> tuple[str, ApiTokenRecord]:
    key = "pair:" + ip

    if _failures(session, key, now) >= MAX_PAIRING_FAILURES_PER_IP:
        raise AuthRefused(
            "throttled", "Too many attempts. Wait 15 minutes, then try again."
        )

    row = session.scalar(
        select(AuthCodeRecord).where(
            AuthCodeRecord.code_hash
            == digest("pairing:" + normalise_code(code)),
            AuthCodeRecord.purpose == "pairing",
        )
    )

    if row is None or row.used_at is not None or _aware(row.expires_at, now) <= now:
        _record(session, [key], False, now)
        raise AuthRefused(
            "invalid_code",
            "That code is not valid. Make a new one in ace, Settings.",
        )

    row.used_at = now
    token = new_token(EXTENSION_PREFIX)
    record = ApiTokenRecord(
        token_hash=digest(token),
        prefix=token[: len(EXTENSION_PREFIX) + 4],
        name=(name.strip() or "Chrome extension")[:80],
        scope=EXTENSION_SCOPE,
        user_id=row.user_id,
        created_at=now,
    )
    session.add(record)
    _record(session, [key], True, now)
    session.flush()
    return token, record


def token_for(
    session: Session,
    token: str,
    *,
    now: datetime,
) -> tuple[ApiTokenRecord, UserRecord] | None:
    if not token.startswith(EXTENSION_PREFIX):
        return None

    row = session.scalar(
        select(ApiTokenRecord).where(ApiTokenRecord.token_hash == digest(token))
    )

    if row is None or row.revoked_at is not None:
        return None

    user = session.get(UserRecord, row.user_id)

    if user is None or not user.is_active:
        return None

    if row.last_used_at is None or now - _aware(row.last_used_at, now) >= TOUCH_EVERY:
        row.last_used_at = now
        session.commit()

    return row, user


def list_tokens(session: Session, user: UserRecord) -> list[ApiTokenRecord]:
    return list(
        session.scalars(
            select(ApiTokenRecord)
            .where(
                ApiTokenRecord.user_id == user.id,
                ApiTokenRecord.revoked_at.is_(None),
            )
            .order_by(ApiTokenRecord.created_at.desc())
        )
    )


def revoke_token(
    session: Session, user: UserRecord, token_id: int, *, now: datetime
) -> bool:
    result = session.execute(
        update(ApiTokenRecord)
        .where(
            ApiTokenRecord.id == token_id,
            ApiTokenRecord.user_id == user.id,
            ApiTokenRecord.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    return bool(result.rowcount)


# ----------------------------------------------------------------------
# Password reset by email
# ----------------------------------------------------------------------


def start_reset(
    session: Session, *, email: str, ip: str, now: datetime
) -> tuple[UserRecord, str] | None:
    """A reset code for the address, or None when there is no such
    account. The caller answers the same either way."""

    key = "reset:" + ip

    if _failures(session, key, now) >= MAX_FAILURES_PER_EMAIL:
        return None

    # Counted as a "failure" so requests are throttled whatever the
    # outcome: a reset request is never something to repeat quickly.
    _record(session, [key], False, now)

    user = find_user(session, email)

    if user is None or not user.is_active:
        return None

    session.execute(
        update(AuthCodeRecord)
        .where(
            AuthCodeRecord.user_id == user.id,
            AuthCodeRecord.purpose == "password_reset",
            AuthCodeRecord.used_at.is_(None),
        )
        .values(used_at=now)
    )
    code = new_code()
    session.add(
        AuthCodeRecord(
            code_hash=digest("reset:" + code),
            purpose="password_reset",
            user_id=user.id,
            created_at=now,
            expires_at=now + RESET_TTL,
        )
    )
    session.flush()
    return user, code


def finish_reset(
    session: Session,
    *,
    email: str,
    code: str,
    password: str,
    ip: str,
    now: datetime,
) -> UserRecord:
    normal_email = _email(email)
    email_key = "reset-code-email:" + normal_email
    ip_key = "reset-code-ip:" + ip
    if (
        _failures(session, email_key, now) >= MAX_CODE_FAILURES_PER_EMAIL
        or _failures(session, ip_key, now) >= MAX_CODE_FAILURES_PER_IP
    ):
        _record(session, [ip_key], False, now)
        raise AuthRefused(
            "throttled",
            "Too many attempts. Wait 15 minutes, then try again.",
        )

    user = find_user(session, normal_email)
    row = session.scalar(
        select(AuthCodeRecord).where(
            AuthCodeRecord.code_hash
            == digest("reset:" + normalise_code(code)),
            AuthCodeRecord.purpose == "password_reset",
        )
    )

    if (
        user is None
        or not user.is_active
        or row is None
        or row.user_id != user.id
        or row.used_at is not None
        or _aware(row.expires_at, now) <= now
    ):
        _record(session, [email_key, ip_key], False, now)
        raise AuthRefused(
            "invalid_code",
            "That reset code is invalid or expired. Request a new code.",
        )

    set_password(session, user, password, now=now)
    row.used_at = now
    _clear(session, email_key)
    _record(session, [email_key], True, now)
    return user
