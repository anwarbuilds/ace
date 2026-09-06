"""SQLAlchemy engine and session factory for ACE."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings


settings = get_settings()


# The scheduler polls several sources at once, each inside its own short
# transaction, so the pool must comfortably exceed scheduler concurrency
# or a worker blocks waiting for a connection rather than for the
# network.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=12,
    max_overflow=8,
    pool_recycle=1800,
)


SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)