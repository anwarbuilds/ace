"""Durable notification-outbox services for ACE."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import (
    Any,
    Protocol,
)

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.app.db.models import NotificationOutboxRecord
from backend.app.evaluation.types import EvaluatedJob
from backend.app.notifications.payload import (
    build_alert_payload,
)
from backend.app.notifications.renderer import render_alert_notification
from backend.app.persistence.hashing import compute_job_content_hash


@dataclass(
    frozen=True,
    slots=True,
)
class OutboxEnqueueResult:
    """Summary of one notification enqueue operation."""

    candidate_count: int

    queued_count: int

    duplicate_count: int


class NotificationOutboxWriter(Protocol):
    """Persistence contract used by the outbox service."""

    def enqueue_if_absent(
        self,
        *,
        dedupe_key: str,
        source: str,
        source_account: str,
        external_id: str,
        observation_status: str,
        job_content_hash: str,
        source_updated_at: datetime | None,
        recipient: str,
        subject: str,
        text_body: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        """Insert one notification unless its event already exists."""


class SqlAlchemyNotificationOutboxRepository:
    """PostgreSQL implementation of the outbox writer.

    Duplicate protection is enforced by PostgreSQL using the unique
    dedupe_key constraint.

    INSERT ... ON CONFLICT DO NOTHING ... RETURNING id is used instead of
    CursorResult.rowcount so insertion detection does not depend on DBAPI
    row-count semantics.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def enqueue_if_absent(
        self,
        *,
        dedupe_key: str,
        source: str,
        source_account: str,
        external_id: str,
        observation_status: str,
        job_content_hash: str,
        source_updated_at: datetime | None,
        recipient: str,
        subject: str,
        text_body: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        """Insert one PENDING outbox row if it does not already exist.

        Returns:
            True when PostgreSQL created the row.
            False when the dedupe key already existed.
        """

        statement = (
            insert(
                NotificationOutboxRecord
            )
            .values(
                dedupe_key=dedupe_key,
                source=source,
                source_account=source_account,
                external_id=external_id,
                observation_status=observation_status,
                job_content_hash=job_content_hash,
                source_updated_at=source_updated_at,
                recipient=recipient,
                subject=subject,
                text_body=text_body,
                payload=payload,
                status="PENDING",
                attempt_count=0,
                digest_id=None,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "dedupe_key",
                ]
            )
            .returning(
                NotificationOutboxRecord.id
            )
        )

        inserted_id = self._session.scalar(
            statement
        )

        return inserted_id is not None


def _require_non_empty(
    value: str,
    *,
    field_name: str,
) -> str:
    """Normalize and validate a required string."""

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return normalized


def _serialize_datetime(
    value: datetime | None,
) -> str | None:
    """Serialize an optional provider timestamp deterministically."""

    if value is None:
        return None

    return value.isoformat()


def build_notification_dedupe_key(
    candidate: EvaluatedJob,
    *,
    source_account: str,
    recipient: str,
) -> str:
    """Build the stable identity of one logical notification event.

    ACE poll time is deliberately excluded.

    Event identity comes from:
    - provider/source identity,
    - external job identity,
    - lifecycle transition,
    - normalized content version,
    - provider update version when available,
    - notification recipient.

    Therefore retrying the same logical event during another process run
    does not create a second notification merely because time advanced.
    """

    normalized_source_account = _require_non_empty(
        source_account,
        field_name="source_account",
    )

    normalized_recipient = _require_non_empty(
        recipient,
        field_name="recipient",
    )

    content_hash = compute_job_content_hash(
        candidate.job
    )

    payload = {
        "source": candidate.job.source,
        "source_account": normalized_source_account,
        "external_id": candidate.job.external_id,
        "observation_status": (
            candidate.observation_status.value
        ),
        "job_content_hash": content_hash,
        "source_updated_at": _serialize_datetime(
            candidate.job.updated_at
        ),
        "recipient": normalized_recipient,
    }

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    return hashlib.sha256(
        serialized.encode(
            "utf-8"
        )
    ).hexdigest()


def enqueue_alert_candidates(
    writer: NotificationOutboxWriter,
    *,
    candidates: Sequence[EvaluatedJob],
    source_account: str,
    recipient: str,
    detected_at: datetime,
) -> OutboxEnqueueResult:
    """Render and durably enqueue ACE alert candidates.

    Each candidate is stored twice over:

    - as pre-rendered single-job text, preserved for auditability and
      for any future per-job delivery path, and
    - as a structured payload, which is what the digest renderer reads.

    detected_at is used only for useful user-facing notification
    information. It is intentionally excluded from deduplication.
    """

    normalized_source_account = _require_non_empty(
        source_account,
        field_name="source_account",
    )

    normalized_recipient = _require_non_empty(
        recipient,
        field_name="recipient",
    )

    queued_count = 0

    duplicate_count = 0

    for candidate in candidates:
        message = render_alert_notification(
            candidate,
            detected_at=detected_at,
        )

        content_hash = compute_job_content_hash(
            candidate.job
        )

        dedupe_key = build_notification_dedupe_key(
            candidate,
            source_account=normalized_source_account,
            recipient=normalized_recipient,
        )

        payload = build_alert_payload(
            candidate,
            source_account=(
                normalized_source_account
            ),
            detected_at=detected_at,
        )

        inserted = writer.enqueue_if_absent(
            dedupe_key=dedupe_key,
            source=candidate.job.source,
            source_account=normalized_source_account,
            external_id=candidate.job.external_id,
            observation_status=(
                candidate.observation_status.value
            ),
            job_content_hash=content_hash,
            source_updated_at=candidate.job.updated_at,
            recipient=normalized_recipient,
            subject=message.subject,
            text_body=message.text_body,
            payload=payload,
        )

        if inserted:
            queued_count += 1
        else:
            duplicate_count += 1

    return OutboxEnqueueResult(
        candidate_count=len(
            candidates
        ),
        queued_count=queued_count,
        duplicate_count=duplicate_count,
    )