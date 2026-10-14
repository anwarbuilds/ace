"""SQLAlchemy engine and session factory for ACE."""

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings


settings = get_settings()


def _engine_options(
    database_url: str,
) -> dict:
    """Return pool settings that suit the database behind the URL.

    The scheduler polls several sources at once, each inside its own
    short transaction, so on PostgreSQL the pool must comfortably exceed
    scheduler concurrency or a worker blocks waiting for a connection
    rather than for the network.

    SQLite runs only the demo database (``backend/scripts/seed_demo.py``)
    so the app can be served where no PostgreSQL exists, such as a cloud
    session. FastAPI serves sync routes from a thread pool, so one
    connection is used from several threads, which SQLite refuses unless
    told otherwise.
    """

    if make_url(
        database_url
    ).get_backend_name() == "sqlite":
        return {
            "connect_args": {
                "check_same_thread": False,
            },
        }

    return {
        "pool_pre_ping": True,
        "pool_size": 12,
        "max_overflow": 8,
        "pool_recycle": 1800,
    }


engine = create_engine(
    settings.database_url,
    **_engine_options(
        settings.database_url
    ),
)


SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)
