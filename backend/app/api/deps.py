"""Dependencies shared by every router."""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal


def get_session() -> Iterator[Session]:
    """Provide one request-scoped session."""

    with SessionLocal() as session:
        yield session
