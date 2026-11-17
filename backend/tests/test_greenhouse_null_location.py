"""A Greenhouse posting whose location is null must not fail the whole board (2026-11-17).

The board and its jobs are fictional.
"""

from __future__ import annotations

import httpx

from backend.app.adapters import greenhouse


def test_a_null_location_is_read_as_unknown(monkeypatch) -> None:
    payload = {
        "jobs": [
            {"id": 1, "title": "Software Engineer I", "location": {"name": None},
             "absolute_url": "https://job-boards.greenhouse.io/northwind/jobs/1", "content": "<p>Build</p>"},
            {"id": 2, "title": "Data Engineer", "location": None,
             "absolute_url": "https://job-boards.greenhouse.io/northwind/jobs/2", "content": ""},
            {"id": 3, "title": "Backend Engineer", "location": {"name": "Denver, CO"},
             "absolute_url": "https://job-boards.greenhouse.io/northwind/jobs/3", "content": ""},
        ]
    }

    def fake_get(url, **kwargs):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(greenhouse.httpx, "get", fake_get)
    jobs, unchanged, _ = greenhouse.fetch_greenhouse_jobs("northwind", "Northwind Robotics")

    assert not unchanged
    assert [job.location for job in jobs] == ["Unknown", "Unknown", "Denver, CO"]
