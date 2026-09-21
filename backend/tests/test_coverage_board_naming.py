"""Which label of a board host is the employer.

On a company's own domain the employer is the last meaningful label:
"cursor.com/careers" is Cursor. On an ATS-hosted board it is the
first, and the last is the software vendor.

Reading it the same way round for both is what filed all 793 of Visa's
postings under the employer name "myworkdayjobs", from a link the user
pasted in themselves.
"""

from __future__ import annotations

import pytest

from backend.app.coverage.service import (
    _name_from_url,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # The case that exposed it.
        (
            "https://visa.wd5.myworkdayjobs.com/en-US/Visa/job/"
            "US---Foster-City-CA/Software-Engineer_REF088543W-1",
            "visa",
        ),
        (
            "https://careers-jobyaviation.icims.com/jobs/search",
            "careers-jobyaviation",
        ),
        (
            "https://twosigma.avature.net/careers",
            "twosigma",
        ),
    ],
)
def test_an_ats_host_names_the_tenant_not_the_vendor(
    url: str,
    expected: str,
) -> None:
    assert _name_from_url(
        url
    ) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://cursor.com/careers/123",
            "cursor",
        ),
        (
            "https://www.ramp.com/careers",
            "ramp",
        ),
        (
            "https://boards.greenhouse.io/datadog",
            "greenhouse",
        ),
    ],
)
def test_a_company_domain_still_names_the_company(
    url: str,
    expected: str,
) -> None:
    """The other direction, or the fix is just "always take the first".

    greenhouse.io is deliberately included: it puts the employer in the
    path, not the host, so this function never decides its name and
    taking the first label there would be wrong too.
    """

    assert _name_from_url(
        url
    ) == expected
