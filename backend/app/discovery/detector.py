"""ATS detection for public ACE job-source discovery.

This module converts a public ATS-hosted job URL into a provider-neutral
source identity.

Detection does NOT verify that the source currently exists and does NOT
persist anything. Verification and persistence remain separate stages.

Examples:

    https://job-boards.greenhouse.io/acme/jobs/123
        -> GREENHOUSE / acme

    https://jobs.lever.co/acme/123
        -> LEVER / acme

    https://jobs.ashbyhq.com/Acme/123
        -> ASHBY / Acme

    https://jobs.smartrecruiters.com/Acme/123-title
        -> SMARTRECRUITERS / Acme
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import (
    unquote,
    urlparse,
)

from backend.app.scheduling.types import (
    SourceType,
)


@dataclass(
    frozen=True,
    slots=True,
)
class DetectedSourceIdentity:
    """ATS identity extracted from one public job or job-board URL."""

    source_type: SourceType
    source_account: str
    source_host: str

    def __post_init__(
        self,
    ) -> None:
        account = (
            self.source_account.strip()
        )

        host = (
            self.source_host
            .strip()
            .lower()
            .rstrip(".")
        )

        if not account:
            raise ValueError(
                "source_account must not be empty."
            )

        if not host:
            raise ValueError(
                "source_host must not be empty."
            )

        object.__setattr__(
            self,
            "source_account",
            account,
        )

        object.__setattr__(
            self,
            "source_host",
            host,
        )


def _prepare_url(
    value: str,
) -> str:
    """Normalize ordinary, scheme-less, and scheme-relative URLs."""

    normalized = value.strip()

    if not normalized:
        return ""

    if normalized.startswith("//"):
        return (
            "https:"
            + normalized
        )

    if "://" not in normalized:
        return (
            "https://"
            + normalized
        )

    return normalized


def _path_segments(
    path: str,
) -> tuple[
    str,
    ...,
]:
    """Return decoded, non-empty URL path segments."""

    result: list[
        str
    ] = []

    for raw_segment in (
        path.split("/")
    ):
        if not raw_segment:
            continue

        segment = (
            unquote(
                raw_segment
            )
            .strip()
        )

        if segment:
            result.append(
                segment
            )

    return tuple(
        result
    )


def _detect_greenhouse(
    *,
    host: str,
    segments: tuple[
        str,
        ...,
    ],
) -> DetectedSourceIdentity | None:
    """Detect Greenhouse-hosted boards and individual postings."""

    is_greenhouse_host = (
        host.endswith(
            ".greenhouse.io"
        )
        and (
            host.startswith(
                "boards."
            )
            or host.startswith(
                "job-boards."
            )
        )
    )

    if (
        not is_greenhouse_host
        or not segments
    ):
        return None

    # Existing ACE Greenhouse identities are normalized lowercase.
    account = (
        segments[
            0
        ].lower()
    )

    return DetectedSourceIdentity(
        source_type=(
            SourceType.GREENHOUSE
        ),
        source_account=account,
        source_host=host,
    )


def _detect_lever(
    *,
    host: str,
    segments: tuple[
        str,
        ...,
    ],
) -> DetectedSourceIdentity | None:
    """Detect Lever-hosted job sites.

    source_host is retained because Lever has multiple hosted regions,
    including the normal and EU job domains.
    """

    valid_hosts = {
        "jobs.lever.co",
        "jobs.eu.lever.co",
    }

    if (
        host not in valid_hosts
        or not segments
    ):
        return None

    return DetectedSourceIdentity(
        source_type=(
            SourceType.LEVER
        ),
        source_account=(
            segments[
                0
            ]
        ),
        source_host=host,
    )


def _detect_ashby(
    *,
    host: str,
    segments: tuple[
        str,
        ...,
    ],
) -> DetectedSourceIdentity | None:
    """Detect Ashby-hosted job boards and postings."""

    if (
        host
        != "jobs.ashbyhq.com"
        or not segments
    ):
        return None

    # Do not lowercase this value.
    #
    # Ashby describes the first path component as the organization's
    # jobs-page name. Preserve the URL representation for later fetches.
    return DetectedSourceIdentity(
        source_type=(
            SourceType.ASHBY
        ),
        source_account=(
            segments[
                0
            ]
        ),
        source_host=host,
    )


def _smartrecruiters_account(
    segments: tuple[
        str,
        ...,
    ],
) -> str | None:
    """Extract a SmartRecruiters company identifier.

    Supported forms include:

        /CompanyName/123-job-title

    and:

        /oneclick-ui/company/CompanyName/publication/<uuid>
    """

    if not segments:
        return None

    if (
        len(
            segments
        )
        >= 3
        and segments[
            0
        ].casefold()
        == "oneclick-ui"
        and segments[
            1
        ].casefold()
        == "company"
    ):
        return segments[
            2
        ]

    return segments[
        0
    ]


def _detect_smartrecruiters(
    *,
    host: str,
    segments: tuple[
        str,
        ...,
    ],
) -> DetectedSourceIdentity | None:
    """Detect SmartRecruiters career and job URLs."""

    valid_hosts = {
        "jobs.smartrecruiters.com",
        "careers.smartrecruiters.com",
    }

    if host not in valid_hosts:
        return None

    account = (
        _smartrecruiters_account(
            segments
        )
    )

    if account is None:
        return None

    return DetectedSourceIdentity(
        source_type=(
            SourceType.SMARTRECRUITERS
        ),
        source_account=account,
        source_host=host,
    )


def detect_source_from_url(
    url: str,
) -> DetectedSourceIdentity | None:
    """Detect the ATS/source identity represented by a public URL.

    Unknown hosts return None rather than raising because public discovery
    documents naturally contain many non-ATS links.
    """

    normalized_url = (
        _prepare_url(
            url
        )
    )

    if not normalized_url:
        return None

    try:
        parsed = urlparse(
            normalized_url
        )

        host = (
            parsed.hostname
            or ""
        ).lower().rstrip(".")

    except ValueError:
        return None

    if not host:
        return None

    segments = (
        _path_segments(
            parsed.path
        )
    )

    detectors = (
        _detect_greenhouse,
        _detect_lever,
        _detect_ashby,
        _detect_smartrecruiters,
    )

    for detector in detectors:
        detected = detector(
            host=host,
            segments=segments,
        )

        if detected is not None:
            return detected

    return None