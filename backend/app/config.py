"""Application configuration for ACE.

Runtime configuration is loaded from environment variables and, during
local development, from the project-level .env file.

Secrets must never be hard-coded into application source code.
"""

from functools import lru_cache
from pydantic import (
    SecretStr,
    field_validator,
)
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






@lru_cache
def get_settings() -> Settings:
    """Return a cached application-settings instance."""

    return Settings()
