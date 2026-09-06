"""Conditional-HTTP support for ACE source polling.

Most job boards publish the same list on consecutive polls. HTTP has a
mechanism for exactly this: the server hands back a validator (an ETag,
or a Last-Modified date), and sending it on the next request lets the
server answer `304 Not Modified` with an empty body.

That skips the download, the JSON parse, and the entire lifecycle diff.
On a catalog where most sources are unchanged most of the time, it is
the cheapest available saving.

Scope
-----

This applies to GET-based providers whose response is a plain document:
Greenhouse, Lever, Ashby, SmartRecruiters and the curated feed. Workday
is excluded because it lists via POST, and Amazon because its search
response is generated per request.

Correctness
-----------

A 304 means the *list* is unchanged, so nothing was added, edited or
closed. The only state that needs updating is the source's
last-success marker. Skipping the diff is therefore safe rather than an
optimisation that trades accuracy for speed.

If a board ignores the validator and returns 200 with an identical body,
nothing breaks -- the normal diff simply finds no changes, at the usual
cost.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(
    frozen=True,
    slots=True,
)
class CacheValidators:
    """HTTP validators remembered from a previous fetch."""

    etag: str | None = None

    last_modified: str | None = None

    @property
    def is_empty(self) -> bool:
        """Return whether there is anything to send."""

        return not (
            self.etag
            or self.last_modified
        )

    def request_headers(
        self,
    ) -> dict[str, str]:
        """Build the conditional request headers."""

        headers: dict[str, str] = {}

        if self.etag:
            headers[
                "If-None-Match"
            ] = self.etag

        if self.last_modified:
            headers[
                "If-Modified-Since"
            ] = self.last_modified

        return headers


def validators_from_response(
    response: httpx.Response,
) -> CacheValidators:
    """Extract the validators a response offers for next time."""

    etag = response.headers.get(
        "etag"
    )

    last_modified = response.headers.get(
        "last-modified"
    )

    return CacheValidators(
        etag=(
            etag.strip()
            if isinstance(
                etag,
                str,
            )
            and etag.strip()
            else None
        ),
        last_modified=(
            last_modified.strip()
            if isinstance(
                last_modified,
                str,
            )
            and last_modified.strip()
            else None
        ),
    )


def is_unchanged(
    response: httpx.Response,
) -> bool:
    """Return whether the server said nothing changed."""

    return response.status_code == 304
