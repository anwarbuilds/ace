from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CanonicalJob(BaseModel):
    """Normalized representation of a job posting inside ACE.

    Every ATS adapter must convert its provider-specific payload into this
    structure before the rest of ACE processes the job.
    """

    model_config = ConfigDict(frozen=True)

    source: str
    company: str

    external_id: str
    requisition_id: str | None = None

    title: str
    location: str
    description: str = ""

    official_url: str

    posted_at: datetime | None = None
    updated_at: datetime | None = None