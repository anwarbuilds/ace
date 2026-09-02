"""Tests for ACE SMTP email delivery."""

from email.message import (
    EmailMessage,
)

import pytest

from backend.app.notifications.email import (
    SmtpEmailConfig,
    SmtpEmailTransport,
)
from backend.app.notifications.types import (
    NotificationMessage,
)


class FakeSMTP:
    """Deterministic SMTP replacement for unit tests."""

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

        self.ehlo_count = 0

        self.starttls_called = False

        self.login_credentials: (
            tuple[str, str] | None
        ) = None

        self.sent_messages: list[
            EmailMessage
        ] = []

    def __enter__(
        self,
    ) -> "FakeSMTP":
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        return None

    def ehlo(self) -> None:
        self.ehlo_count += 1

    def starttls(
        self,
        *,
        context,
    ) -> None:
        assert context is not None

        self.starttls_called = True

    def login(
        self,
        username: str,
        password: str,
    ) -> None:
        self.login_credentials = (
            username,
            password,
        )

    def send_message(
        self,
        message: EmailMessage,
    ) -> None:
        self.sent_messages.append(
            message
        )


def test_smtp_transport_sends_authenticated_starttls_email(
    monkeypatch,
) -> None:
    instances: list[
        FakeSMTP
    ] = []

    def fake_factory(
        *,
        host: str,
        port: int,
        timeout: float,
    ) -> FakeSMTP:
        instance = FakeSMTP(
            host,
            port,
            timeout,
        )

        instances.append(
            instance
        )

        return instance

    monkeypatch.setattr(
        (
            "backend.app.notifications."
            "email.smtplib.SMTP"
        ),
        fake_factory,
    )

    config = SmtpEmailConfig(
        host="smtp.example.com",
        port=587,
        username="ace@example.com",
        password="secret",
        from_email="ace@example.com",
        use_starttls=True,
        timeout_seconds=10.0,
    )

    transport = SmtpEmailTransport(
        config
    )

    message = NotificationMessage(
        subject="[ACE] Test",
        text_body="Hello from ACE.",
    )

    transport.send(
        message,
        recipient="user@example.com",
    )

    assert len(
        instances
    ) == 1

    smtp = instances[
        0
    ]

    assert (
        smtp.host
        == "smtp.example.com"
    )

    assert smtp.port == 587

    assert smtp.timeout == 10.0

    assert smtp.starttls_called is True

    assert smtp.ehlo_count == 2

    assert (
        smtp.login_credentials
        == (
            "ace@example.com",
            "secret",
        )
    )

    assert len(
        smtp.sent_messages
    ) == 1

    sent = smtp.sent_messages[
        0
    ]

    assert (
        sent["Subject"]
        == "[ACE] Test"
    )

    assert (
        sent["From"]
        == "ace@example.com"
    )

    assert (
        sent["To"]
        == "user@example.com"
    )

    assert (
        "Hello from ACE."
        in sent.get_content()
    )


def test_smtp_transport_supports_no_auth_and_no_starttls(
    monkeypatch,
) -> None:
    instances: list[
        FakeSMTP
    ] = []

    def fake_factory(
        *,
        host: str,
        port: int,
        timeout: float,
    ) -> FakeSMTP:
        instance = FakeSMTP(
            host,
            port,
            timeout,
        )

        instances.append(
            instance
        )

        return instance

    monkeypatch.setattr(
        (
            "backend.app.notifications."
            "email.smtplib.SMTP"
        ),
        fake_factory,
    )

    config = SmtpEmailConfig(
        host="localhost",
        port=1025,
        from_email="ace@example.com",
        use_starttls=False,
    )

    transport = SmtpEmailTransport(
        config
    )

    transport.send(
        NotificationMessage(
            subject="Test",
            text_body="Body",
        ),
        recipient="user@example.com",
    )

    smtp = instances[
        0
    ]

    assert (
        smtp.starttls_called
        is False
    )

    assert (
        smtp.login_credentials
        is None
    )

    assert smtp.ehlo_count == 1

    assert len(
        smtp.sent_messages
    ) == 1


@pytest.mark.parametrize(
    (
        "username",
        "password",
    ),
    [
        (
            "ace@example.com",
            None,
        ),
        (
            None,
            "secret",
        ),
    ],
)
def test_smtp_config_rejects_partial_credentials(
    username: str | None,
    password: str | None,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "username and password"
        ),
    ):
        SmtpEmailConfig(
            host="smtp.example.com",
            port=587,
            username=username,
            password=password,
            from_email="ace@example.com",
        )


def test_smtp_transport_rejects_blank_recipient() -> None:
    config = SmtpEmailConfig(
        host="smtp.example.com",
        port=587,
        from_email="ace@example.com",
        use_starttls=False,
    )

    transport = SmtpEmailTransport(
        config
    )

    with pytest.raises(
        ValueError,
        match="recipient",
    ):
        transport.send(
            NotificationMessage(
                subject="Test",
                text_body="Body",
            ),
            recipient="   ",
        )