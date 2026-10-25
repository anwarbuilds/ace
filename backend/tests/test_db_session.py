"""Connection options for the application's database engine."""

from backend.app.db.session import _engine_options


def test_postgres_connections_switch_jit_off() -> None:
    """Compiling a query cost more than running it.

    On the 971,490-job corpus, PostgreSQL's JIT took 536 ms of a 582 ms
    queue count, and an Opportunities page ran seven such queries.
    """

    options = _engine_options(
        "postgresql+psycopg://ace:ace@localhost:5432/ace"
    )

    assert options["connect_args"]["options"] == "-c jit=off"

    # The pool sizing the scheduler depends on is unchanged.
    assert options["pool_size"] == 12
    assert options["pool_pre_ping"] is True


def test_sqlite_demo_gets_only_its_thread_option() -> None:
    """SQLite has no JIT, and would reject a PostgreSQL option."""

    assert _engine_options("sqlite:///ace-demo.db") == {
        "connect_args": {
            "check_same_thread": False,
        },
    }
