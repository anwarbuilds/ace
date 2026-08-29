from datetime import datetime

from pydantic import BaseModel


class CanonicalJob(BaseModel):
    source: str
    company: str
    external_id: str
    requisition_id: str | None = None

    title: str
    location: str

    official_url: str

    posted_at: datetime | None = None
    updated_at: datetime | None = None