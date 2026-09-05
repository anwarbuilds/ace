"""Shared test configuration for ACE.

The test suite must not depend on a developer's local .env file.

Some modules (the CLI scripts, and anything importing db.session) build
Settings at import time, which requires DATABASE_URL. Tests never open a
real PostgreSQL connection -- database-backed tests create their own
in-memory SQLite engines -- but the setting still has to resolve for
collection to succeed.

Providing an inert default here keeps the suite hermetic, so a clean
checkout or a CI runner with no .env behaves exactly like a developer
machine.
"""

import os


# Set before any test module imports application code.
os.environ.setdefault(
    "DATABASE_URL",
    (
        "postgresql+psycopg://"
        "ace:ace@localhost:5432/"
        "ace_test_placeholder"
    ),
)

os.environ.setdefault(
    "NOTIFICATION_DIGEST_TIMEZONE",
    "America/Los_Angeles",
)

os.environ.setdefault(
    "NOTIFICATION_DIGEST_TIMES",
    "07:30,17:30",
)
