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

    # Only a handful of providers expose this at all, so it is left
    # unset rather than guessed at: None means "the source did not
    # say", never "full-time assumed". Adzuna reports it directly as
    # "contract_type"; most ATS boards never surface an equivalent
    # field and this stays None for them.
    employment_type: str | None = None