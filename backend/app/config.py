"""Application configuration for ACE.

Runtime configuration is loaded from environment variables and, during
local development, from the project-level .env file.

Secrets must never be hard-coded into application source code.
"""

from functools import lru_cache

from pydantic import SecretStr
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

    smtp_host: str = "smtp.gmail.com"

    smtp_port: int = 587

    smtp_username: str | None = None

    smtp_password: SecretStr | None = None

    smtp_from_email: str | None = None

    notification_to_email: str | None = None

    smtp_use_starttls: bool = True

    smtp_timeout_seconds: float = 20.0


@lru_cache
def get_settings() -> Settings:
    """Return a cached application-settings instance."""

    return Settings()