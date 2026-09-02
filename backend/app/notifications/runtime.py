"""Runtime composition helpers for ACE notifications."""

from backend.app.config import (
    Settings,
)
from backend.app.notifications.email import (
    SmtpEmailConfig,
    SmtpEmailTransport,
)


def require_notification_recipient(
    settings: Settings,
) -> str:
    """Return the configured notification recipient."""

    recipient = (
        settings.notification_to_email
        or ""
    ).strip()

    if not recipient:
        raise ValueError(
            (
                "NOTIFICATION_TO_EMAIL "
                "is not configured."
            )
        )

    return recipient


def build_smtp_transport_from_settings(
    settings: Settings,
) -> SmtpEmailTransport:
    """Construct ACE's SMTP transport from application settings."""

    username = (
        settings.smtp_username
        or ""
    ).strip()

    if not username:
        raise ValueError(
            (
                "SMTP_USERNAME is not "
                "configured."
            )
        )

    if settings.smtp_password is None:
        raise ValueError(
            (
                "SMTP_PASSWORD is not "
                "configured."
            )
        )

    password = (
        settings.smtp_password
        .get_secret_value()
    )

    if not password:
        raise ValueError(
            (
                "SMTP_PASSWORD is not "
                "configured."
            )
        )

    from_email = (
        settings.smtp_from_email
        or username
    ).strip()

    if not from_email:
        raise ValueError(
            (
                "SMTP_FROM_EMAIL is not "
                "configured."
            )
        )

    config = SmtpEmailConfig(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=username,
        password=password,
        from_email=from_email,
        use_starttls=(
            settings.smtp_use_starttls
        ),
        timeout_seconds=(
            settings.smtp_timeout_seconds
        ),
    )

    return SmtpEmailTransport(
        config
    )