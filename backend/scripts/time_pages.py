"""Time every API request the workspace pages make, without changing anything.

Run inside the API container, against the real database:

    docker compose --env-file .env -f deploy/oracle/compose.yaml \\
        exec -T api python -m backend.scripts.time_pages

or, before this file is in the image, piped from a checkout:

    ... exec -T api python - < backend/scripts/time_pages.py

It prints paths, status codes, response sizes and milliseconds, never a
row. Every database connection it opens is read-only, so a request that
tried to write would fail rather than change anything. It calls the
application in-process as a local caller, so no session is created and
the running API is not involved.
"""

from __future__ import annotations

import statistics
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from backend.app.db.session import engine


if engine.dialect.name == "postgresql":

    @event.listens_for(engine, "connect")
    def _read_only(dbapi_connection, _record) -> None:
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET default_transaction_read_only = on")
        dbapi_connection.commit()


from fastapi.testclient import TestClient  # noqa: E402

from backend.app.api.main import app  # noqa: E402
from backend.app.auth.guard import Principal, require_auth  # noqa: E402


QUEUE = "sort=new_grad_first,unapplied_first,best_match&limit=50"


def pages() -> dict[str, list[str]]:
    """What each page asks for, as the website asks it."""

    since = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "Shell (every full load)": ["/api/auth/status", "/api/system", "/api/marks", "/api/answers"],
        "Pulls": ["/api/pulls?tz=America/Los_Angeles&filter=all"],
        "Opportunities": [
            "/api/sessions?limit=30",
            f"/api/jobs?{QUEUE}&offset=0",
            "/api/stats",
            f"/api/jobs?since={since}&limit=1",
        ],
        "Opportunities, page 2": [f"/api/jobs?{QUEUE}&offset=50", "/api/stats"],
        "Opportunities, filter menu": ["/api/facets"],
        "Applications": [
            "/api/sessions?limit=30",
            "/api/jobs?sort=newest&limit=50&offset=0&mark=applied",
            "/api/stats",
            "/api/applications/external",
            "/api/dashboard",
        ],
        "Analytics": ["/api/dashboard?days=14"],
        "Career Dashboard": ["/api/intelligence?days=90"],
        "Resume Studio": ["/api/studio", "/api/resume", "/api/stats"],
        "Skills": ["/api/resume", "/api/stats", "/api/facets"],
        "Coverage": ["/api/coverage"],
        "Settings": ["/api/facets", "/api/resume", "/api/marks", "/api/system"],
        "Live check, every 2 minutes": ["/api/sessions?limit=30&jobs_per_session=6"],
    }


def main() -> int:
    app.dependency_overrides[require_auth] = lambda: Principal(kind="local")
    # No context manager: the application's startup hooks do not run.
    client = TestClient(app)
    seen: dict[str, tuple[int, int, float]] = {}

    for page, paths in pages().items():
        print(page)
        slowest = 0.0
        for path in paths:
            if path not in seen:
                runs = []
                for _ in range(3):
                    started = time.perf_counter()
                    response = client.get(path)
                    runs.append((time.perf_counter() - started) * 1000)
                seen[path] = (response.status_code, len(response.content), statistics.median(runs))
            status, size, ms = seen[path]
            slowest = max(slowest, ms)
            print(f"  {ms:7.0f} ms  {status}  {size / 1024:7.1f} KB  {path.split('?')[0]}")
        print(f"  {slowest:7.0f} ms  slowest request (the page's requests run in parallel)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
