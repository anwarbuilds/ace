"""Transport-neutral notification types for ACE."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    """Rendered notification ready for a delivery transport.

    The notification layer deliberately does not know whether the message
    will later be delivered through email, push notification, SMS, or
    another transport.
    """

    subject: str

    text_body: str