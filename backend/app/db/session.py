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

    PostgreSQL's JIT is switched off. The queue's queries carry several
    correlated subqueries, so the planner's cost estimate passes the JIT
    threshold although each one touches a few thousand rows: on the
    971,490-job corpus, compiling took 536 ms of a 582 ms count, and one
    Opportunities page ran seven such queries. With JIT off the same
    count took 51 ms, and moving to page 2 stopped taking seconds.
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
        "connect_args": {
            "options": "-c jit=off",
        },
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
