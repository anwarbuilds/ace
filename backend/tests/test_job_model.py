from backend.app.models.job import CanonicalJob


def test_canonical_job_creation():
    job = CanonicalJob(
        source="greenhouse",
        company="Example",
        external_id="123",
        title="Software Engineer",
        location="Seattle, WA",
        official_url="https://example.com/jobs/123",
    )

    assert job.company == "Example"
    assert job.title == "Software Engineer"
    assert job.external_id == "123"