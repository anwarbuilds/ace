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

    display_timezone: str = (
        "America/Los_Angeles"
    )


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


@lru_cache
def get_settings() -> Settings:
    """Return a cached application-settings instance."""

    return Settings()
