import httpx

from backend.app.models.job import CanonicalJob


GREENHOUSE_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"


def fetch_greenhouse_jobs(
    board_token: str,
    company_name: str,
) -> list[CanonicalJob]:

    url = f"{GREENHOUSE_BASE_URL}/{board_token}/jobs"

    response = httpx.get(
        url,
        timeout=20.0,
    )

    response.raise_for_status()

    payload = response.json()

    jobs = []

    for raw_job in payload["jobs"]:
        job = CanonicalJob(
            source="greenhouse",
            company=company_name,
            external_id=str(raw_job["id"]),
            requisition_id=raw_job.get("requisition_id"),
            title=raw_job["title"],
            location=raw_job.get("location", {}).get("name", "Unknown"),
            official_url=raw_job["absolute_url"],
            posted_at=raw_job.get("first_published"),
            updated_at=raw_job.get("updated_at"),
        )

        jobs.append(job)

    return jobs