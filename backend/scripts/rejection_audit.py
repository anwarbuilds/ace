"""What ACE is throwing away, and why: python -m backend.scripts.rejection_audit

A false rejection is invisible. The queue looks healthy, no error is
logged, and the only signal is the user noticing a job somewhere else
that should have been here. That is how a Stripe posting located "US"
sat rejected as "outside US" for two days.

This turns the silence into a list. It cannot know which rejections are
wrong, so it does not guess: it shows the reasons in order and the
values behind the ones that hinge on a lookup table, because a table is
never finished and its gaps are what produce silent losses.

Read the location section as a to-do list. Anything in it that is
plainly a US place is a job being thrown away right now.

    --reason CODE   drill into one reason
    --limit N       how many distinct values to show
"""

from __future__ import annotations

import argparse
import re
from collections import Counter

from sqlalchemy import select

from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
)
from backend.app.db.session import SessionLocal


# Values that are honestly unresolvable from the location string, as
# opposed to values a lookup table failed to recognise. Separated so
# the second list stays short enough to read.
UNRESOLVABLE = re.compile(
    r"^\s*(?:unknown|n/?a|hybrid|remote|in.?office|"
    r"multiple|various|tbd|-+|\d+\s+locations?)\s*$",
    re.IGNORECASE,
)


# Places that are clearly not the US, so they do not need reviewing.
CLEARLY_FOREIGN = re.compile(
    r"india|singapore|london|dublin|ireland|canada|toronto|"
    r"germany|berlin|france|paris|japan|tokyo|china|beijing|"
    r"shanghai|australia|sydney|brazil|mexico|spain|netherlands|"
    r"amsterdam|poland|israel|korea|taiwan|switzerland|sweden|"
    r"norway|denmark|italy|portugal|romania|ukraine|philippines|"
    r"vietnam|indonesia|thailand|malaysia|argentina|chile|"
    r"colombia|peru|uae|dubai|nigeria|kenya|egypt|turkey|greece|"
    r"austria|belgium|czech|hungary|finland|bulgaria|croatia|"
    r"serbia|estonia|latvia|lithuania|slovak|sloven|scotland|"
    r"wales|england|bengaluru|hyderabad|pune|mumbai|delhi|"
    r"chennai|gurgaon|noida|emea|apac|worldwide|europe|zurich|"
    r"munich|hamburg|vienna|prague|warsaw|lisbon|madrid|milan|"
    r"stockholm|copenhagen|helsinki|oslo|athens|bucharest|sofia|"
    r"zagreb|tallinn|riga|vilnius|bratislava|ljubljana|hong kong|"
    r"\bind-|\buk\b|\beu\b",
    re.IGNORECASE,
)


def main() -> int:
    """Print why active postings are being rejected."""

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--reason",
        default=None,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
    )

    args = parser.parse_args()

    reasons: Counter = Counter()

    locations: Counter = Counter()

    unresolvable = 0

    total = 0

    rejected = 0

    with SessionLocal() as session:
        rows = session.execute(
            select(
                JobRecord.location,
                JobEvaluationRecord
                .eligibility_status,
                JobEvaluationRecord
                .reason_codes,
            )
            .join(
                JobEvaluationRecord,
                JobEvaluationRecord.job_id
                == JobRecord.id,
            )
            .where(
                JobRecord.is_active.is_(
                    True
                )
            )
        ).all()

    for location, status, codes in rows:
        total += 1

        if status != "REJECT":
            continue

        rejected += 1

        for code in codes or ():
            reasons[code] += 1

        if args.reason and args.reason not in (
            codes or ()
        ):
            continue

        if "OUTSIDE_US" not in (
            codes or ()
        ):
            continue

        value = (
            location or ""
        ).strip() or "(blank)"

        if UNRESOLVABLE.match(
            value
        ):
            unresolvable += 1

            continue

        if CLEARLY_FOREIGN.search(
            value
        ):
            continue

        locations[value] += 1

    print(
        f"{rejected:,} of {total:,} active "
        "postings are rejected\n"
    )

    print(
        "WHY"
    )

    for code, count in reasons.most_common():
        print(
            f"  {code:24} {count:7,}"
        )

    print(
        "\nLOCATIONS REJECTED AS NON-US, "
        "excluding clearly foreign and "
        f"{unresolvable:,} unresolvable"
    )

    if not locations:
        print(
            "  nothing left to review."
        )

        return 0

    print(
        "  Anything here that is a US place "
        "is a job being thrown away.\n"
    )

    for value, count in locations.most_common(
        args.limit
    ):
        print(
            f"  {value[:46]:46} {count:6,}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
