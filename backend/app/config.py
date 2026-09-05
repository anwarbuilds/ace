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

from pydantic import (
    SecretStr,
    field_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from backend.app.notifications.schedule import (
    DigestWindowSchedule,
    parse_digest_times,
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

    smtp_host: str = "smtp.gmail.com"

    smtp_port: int = 587

    smtp_username: str | None = None

    smtp_password: SecretStr | None = None

    smtp_from_email: str | None = None

    notification_to_email: str | None = None

    smtp_use_starttls: bool = True

    smtp_timeout_seconds: float = 20.0

    # ------------------------------------------------------------------
    # Alert freshness policy
    # ------------------------------------------------------------------
    #
    # ACE persists every discovered job. Freshness controls only whether
    # a newly observed job is worth interrupting the user about.
    #
    # A job that fails freshness remains in the database and remains
    # available to the web application.

    max_alert_posting_age_days: int = 30

    alert_on_unknown_posting_age: bool = False

    # ------------------------------------------------------------------
    # Digest delivery policy
    # ------------------------------------------------------------------

    notification_digest_timezone: str = (
        "America/Los_Angeles"
    )

    notification_digest_times: str = (
        "07:30,17:30"
    )

    notification_digest_max_jobs: int = 100

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
        "notification_digest_max_jobs"
    )
    @classmethod
    def _validate_digest_max_jobs(
        cls,
        value: int,
    ) -> int:
        """Require at least one job per digest email."""

        if value < 1:
            raise ValueError(
                (
                    "NOTIFICATION_DIGEST_MAX_JOBS "
                    "must be at least 1."
                )
            )

        return value

    @field_validator(
        "notification_digest_timezone"
    )
    @classmethod
    def _validate_digest_timezone(
        cls,
        value: str,
    ) -> str:
        """Require a resolvable IANA timezone name."""

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                (
                    "NOTIFICATION_DIGEST_TIMEZONE "
                    "must not be empty."
                )
            )

        try:
            ZoneInfo(
                normalized
            )

        except (
            ZoneInfoNotFoundError,
            ValueError,
        ) as exc:
            raise ValueError(
                (
                    "NOTIFICATION_DIGEST_TIMEZONE "
                    f"is not a known timezone: "
                    f"{normalized!r}."
                )
            ) from exc

        return normalized

    @field_validator(
        "notification_digest_times"
    )
    @classmethod
    def _validate_digest_times(
        cls,
        value: str,
    ) -> str:
        """Require one or two valid HH:MM digest window times."""

        parse_digest_times(
            value
        )

        return value.strip()

    @property
    def digest_schedule(
        self,
    ) -> DigestWindowSchedule:
        """Return the validated digest window schedule."""

        return DigestWindowSchedule(
            timezone_name=(
                self.notification_digest_timezone
            ),
            times=parse_digest_times(
                self.notification_digest_times
            ),
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached application-settings instance."""

    return Settings()
