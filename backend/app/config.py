"""Application configuration for ACE.

Runtime configuration is loaded from environment variables and, during
local development, from the project-level .env file.

Secrets must never be hard-coded into application source code.
"""

from functools import lru_cache
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

from pydantic import field_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)



class Settings(BaseSettings):
    """Runtime configuration required by the ACE backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str


    # ------------------------------------------------------------------
    # Alert freshness policy
    # ------------------------------------------------------------------
    #
    # ACE persists every discovered job. Freshness controls only whether
    # a newly observed job is worth interrupting the user about.
    #
    # A job that fails freshness remains in the database and remains
    # available to the web application.

    max_alert_posting_age_days: int = 10

    alert_on_unknown_posting_age: bool = False


    # ------------------------------------------------------------------
    # How dates are written for a person to read
    # ------------------------------------------------------------------
    #
    # Instants are stored in UTC and that does not change. This is only
    # for rendering a calendar date server-side, which is a different
    # question: "which day was this, where the user was standing".
    #
    # The web client never had this problem, because it formats from an
    # ISO string in the browser and picks up the reader's own zone. The
    # CSV export did: it wrote UTC directly, so an application marked at
    # 19:43 on a Tuesday in Seattle exported as Wednesday, because UTC
    # had already rolled over. The user saw one date in ACE and a
    # different one in the sheet ACE handed them.

    # Outbound mail for job alerts. ACE deleted its whole email
    # subsystem on 2026-09-06 because the web application was the only
    # surface being watched. This does not restore that: there is no
    # outbox, no delivery worker and no retries. It is one HTTPS call
    # per pull, because the reason changed -- alerts now exist so an
    # application can be started from a phone, away from the laptop.
    #
    # HTTPS rather than SMTP because cloud providers routinely block
    # outbound 25 and 587, which is where self-hosted SMTP dies.
    resend_api_key: str = ""

    # Must be an address on a domain verified with the provider.
    # Resend's onboarding@resend.dev works for testing and can only
    # deliver to the account owner's own address.
    mail_from: str = "ACE <onboarding@resend.dev>"

    # Where alerts go. Blank disables sending entirely.
    alert_email: str = ""

    # How ACE refers to itself in links inside an email. Without this
    # a link would have to be built from a request, and an alert is
    # sent by the scheduler where there is no request to build from.
    public_base_url: str = "http://localhost:3000"

    display_timezone: str = (
        "America/Los_Angeles"
    )

    # ------------------------------------------------------------------
    # Sign-in
    # ------------------------------------------------------------------
    #
    # required: every /api/ route except sign-in itself and /healthz
    # needs the owner's browser session or a paired extension token.
    #
    # disabled: the rollback switch, kept because the first attempt at
    # auth (September 2026) locked the extension out and had to be
    # reverted. It answers only requests from this computer or a
    # private network, never one forwarded from a public address, so
    # switching it on cannot expose a cloud deployment.
    ace_auth: str = "required"

    # First-run account creation in the browser is allowed from this
    # computer or a private network. On a server reached over the
    # internet, set this and type it on the setup page, so nobody who
    # finds the address first can claim the account.
    setup_token: str = ""

    # A browser session lasts this long, then the owner signs in again.
    session_days: int = 30

    # Fail closed when password sign-in cannot deliver its one-time email
    # code. Keep false only for local development without a mail provider.
    require_login_email_code: bool = False

    # Where the Next.js app is served for OAuth redirects and web links.
    web_base_url: str = "http://localhost:3000"

    # Optional owner-only Google OpenID Connect. The owner account must
    # already exist and Google's verified email must match it exactly.
    # The first successful sign-in binds the Google subject to that
    # owner; later sign-ins must present the same subject.
    google_client_id: str = ""

    google_client_secret: str = ""

    google_redirect_uri: str = ""

    # Separate opt-in Gmail read-only authorization. Reuse no sign-in grant.
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = ""
    # A Fernet key supplied privately by the owner, never committed.
    gmail_token_key: str = ""
    gmail_auto_outcomes_allowed: bool = False
    # A clear rejection matched to exactly one application is recorded
    # without a manual step (owner decision, 2026-10-26). False sends
    # every rejection back to review.
    gmail_auto_rejections: bool = True
    # A parser release must not implicitly authorize rewriting saved mail.
    # Enable only for an owner-approved historical reclassification operation.
    gmail_historical_rechecks_enabled: bool = False
    # Existing ready grants may check new mail while the website is closed.
    # New grants remain paused; the owner can pause/disconnect at any time.
    gmail_background_sync_enabled: bool = True

    # The interactive API docs list every route. Off unless asked for.
    api_docs: bool = False


    @field_validator(
        "max_alert_posting_age_days"
    )
    @classmethod
    def _validate_max_alert_posting_age_days(
        cls,
        value: int,
    ) -> int:
        """Require a strictly positive freshness threshold."""

        if value < 1:
            raise ValueError(
                (
                    "MAX_ALERT_POSTING_AGE_DAYS "
                    "must be at least 1."
                )
            )

        return value


    @field_validator(
        "display_timezone"
    )
    @classmethod
    def _validate_display_timezone(
        cls,
        value: str,
    ) -> str:
        """Require a zone the system can actually resolve.

        Refused at startup rather than at render time. A bad zone name
        would otherwise surface as a stack trace midway through writing
        a spreadsheet, or worse, be silently swallowed and fall back to
        UTC -- which is the bug this setting exists to fix.
        """

        try:
            ZoneInfo(
                value
            )
        except (
            ZoneInfoNotFoundError,
            ValueError,
        ) as error:
            raise ValueError(
                (
                    "DISPLAY_TIMEZONE must be "
                    "an IANA zone name such "
                    "as America/Los_Angeles."
                )
            ) from error

        return value


    @field_validator(
        "ace_auth"
    )
    @classmethod
    def _validate_ace_auth(
        cls,
        value: str,
    ) -> str:
        """Refuse a typo rather than guess which way it was meant."""

        value = value.strip().lower()

        if value not in ("required", "disabled"):
            raise ValueError(
                "ACE_AUTH must be required or disabled."
            )

        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached application-settings instance."""

    return Settings()
