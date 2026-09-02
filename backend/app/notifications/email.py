"""SMTP email delivery transport for ACE."""

from dataclasses import dataclass
from email.message import EmailMessage
import smtplib
import ssl

from backend.app.notifications.types import (
    NotificationMessage,
)


@dataclass(
    frozen=True,
    slots=True,
)
class SmtpEmailConfig:
    """Configuration required for SMTP delivery."""

    host: str

    port: int

    from_email: str

    username: str | None = None

    password: str | None = None

    use_starttls: bool = True

    timeout_seconds: float = 20.0

    def __post_init__(self) -> None:
        """Validate SMTP configuration."""

        if not self.host.strip():
            raise ValueError(
                "SMTP host must not be empty."
            )

        if not (
            1
            <= self.port
            <= 65535
        ):
            raise ValueError(
                "SMTP port must be between 1 and 65535."
            )

        if not self.from_email.strip():
            raise ValueError(
                "SMTP from_email must not be empty."
            )

        if self.timeout_seconds <= 0:
            raise ValueError(
                (
                    "SMTP timeout_seconds "
                    "must be greater than zero."
                )
            )

        username_present = bool(
            self.username
            and self.username.strip()
        )

        password_present = bool(
            self.password
        )

        if (
            username_present
            != password_present
        ):
            raise ValueError(
                (
                    "SMTP username and password "
                    "must either both be configured "
                    "or both be omitted."
                )
            )


class SmtpEmailTransport:
    """Deliver rendered ACE notifications over SMTP."""

    def __init__(
        self,
        config: SmtpEmailConfig,
    ) -> None:
        self._config = config

    def send(
        self,
        message: NotificationMessage,
        *,
        recipient: str,
    ) -> None:
        """Deliver one notification message."""

        normalized_recipient = (
            recipient.strip()
        )

        if not normalized_recipient:
            raise ValueError(
                (
                    "Notification recipient "
                    "must not be empty."
                )
            )

        email_message = EmailMessage()

        email_message[
            "Subject"
        ] = message.subject

        email_message[
            "From"
        ] = self._config.from_email

        email_message[
            "To"
        ] = normalized_recipient

        email_message.set_content(
            message.text_body
        )

        with smtplib.SMTP(
            host=self._config.host,
            port=self._config.port,
            timeout=(
                self._config.timeout_seconds
            ),
        ) as smtp:
            smtp.ehlo()

            if (
                self._config.use_starttls
            ):
                context = (
                    ssl.create_default_context()
                )

                smtp.starttls(
                    context=context
                )

                smtp.ehlo()

            if (
                self._config.username
                is not None
            ):
                smtp.login(
                    self._config.username,
                    self._config.password,
                )

            smtp.send_message(
                email_message
            )