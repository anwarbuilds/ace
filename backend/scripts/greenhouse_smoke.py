"""Manual Greenhouse + ACE eligibility integration smoke test.

This diagnostic intentionally calls the live Greenhouse API.

It validates:
1. ATS ingestion
2. role-family classification
3. deterministic eligibility decisions
4. rejection reasons for target-role opportunities

It is not part of the automated unit-test suite.
"""

from collections import Counter

from backend.app.adapters.greenhouse import (
    fetch_greenhouse_jobs,
)
from backend.app.intelligence.eligibility import (
    EligibilityStatus,
    evaluate_job,
)
from backend.app.intelligence.roles import (
    RoleFamily,
)


def main() -> None:
    jobs = fetch_greenhouse_jobs(
        board_token="databricks",
        company_name="Databricks",
    )

    evaluated_jobs = [
        (
            job,
            evaluate_job(job),
        )
        for job in jobs
    ]

    target_jobs = [
        (
            job,
            decision,
        )
        for job, decision in evaluated_jobs
        if decision.role_family != RoleFamily.OTHER
    ]

    qualifying_jobs = [
        (
            job,
            decision,
        )
        for job, decision in target_jobs
        if decision.status
        in {
            EligibilityStatus.PASS,
            EligibilityStatus.STRETCH,
        }
    ]

    rejected_target_jobs = [
        (
            job,
            decision,
        )
        for job, decision in target_jobs
        if decision.status == EligibilityStatus.REJECT
    ]

    status_counts = Counter(
        decision.status.value
        for _, decision in evaluated_jobs
    )

    detected_role_counts = Counter(
        decision.role_family.value
        for _, decision in target_jobs
    )

    qualifying_role_counts = Counter(
        decision.role_family.value
        for _, decision in qualifying_jobs
    )

    target_rejection_reason_counts = Counter(
        reason_code.value
        for _, decision in rejected_target_jobs
        for reason_code in decision.reason_codes
    )

    print()
    print("ACE Greenhouse eligibility audit")
    print("=" * 88)

    print(f"Total Databricks jobs:         {len(jobs)}")
    print(f"Detected target-role jobs:     {len(target_jobs)}")
    print(f"Qualifying target-role jobs:   {len(qualifying_jobs)}")

    print()
    print("Overall eligibility")
    print("=" * 88)

    print(
        f"PASS:                          "
        f"{status_counts[EligibilityStatus.PASS.value]}"
    )

    print(
        f"STRETCH:                       "
        f"{status_counts[EligibilityStatus.STRETCH.value]}"
    )

    print(
        f"REJECT:                        "
        f"{status_counts[EligibilityStatus.REJECT.value]}"
    )

    print()
    print("Target roles detected BEFORE eligibility")
    print("=" * 88)

    print(
        "Software Engineering:          "
        f"{detected_role_counts['SOFTWARE_ENGINEERING']}"
    )

    print(
        "AI / ML Engineering:           "
        f"{detected_role_counts['AI_ML_ENGINEERING']}"
    )

    print(
        "Forward Deployed Engineering:  "
        f"{detected_role_counts['FORWARD_DEPLOYED_ENGINEERING']}"
    )

    print()
    print("Target roles surviving eligibility")
    print("=" * 88)

    print(
        "Software Engineering:          "
        f"{qualifying_role_counts['SOFTWARE_ENGINEERING']}"
    )

    print(
        "AI / ML Engineering:           "
        f"{qualifying_role_counts['AI_ML_ENGINEERING']}"
    )

    print(
        "Forward Deployed Engineering:  "
        f"{qualifying_role_counts['FORWARD_DEPLOYED_ENGINEERING']}"
    )

    print()
    print("Why TARGET roles were rejected")
    print("=" * 88)

    for reason, count in target_rejection_reason_counts.most_common():
        print(
            f"{reason:<34} {count}"
        )

    print()
    print("Sample rejected TARGET roles")
    print("=" * 88)

    for job, decision in rejected_target_jobs[:20]:
        print("-" * 88)

        print(
            f"Role family:  "
            f"{decision.role_family.value}"
        )

        print(f"Title:        {job.title}")
        print(f"Location:     {job.location}")

        print(
            f"Experience:   "
            f"{decision.required_experience_years}"
        )

        print(
            f"Reasons:      "
            f"{'; '.join(decision.reasons)}"
        )

    print()
    print("ALL qualifying opportunities")
    print("=" * 88)

    for job, decision in qualifying_jobs:
        print("-" * 88)

        print(
            f"Decision:     "
            f"{decision.status.value}"
        )

        print(
            f"Role family:  "
            f"{decision.role_family.value}"
        )

        print(
            f"Priority:     "
            f"{decision.role_priority.value}"
        )

        print(f"Company:      {job.company}")
        print(f"Title:        {job.title}")
        print(f"Location:     {job.location}")

        print(
            f"Experience:   "
            f"{decision.required_experience_years}"
        )

        print(
            f"Reason:       "
            f"{'; '.join(decision.reasons)}"
        )

        print(
            f"Official URL: "
            f"{job.official_url}"
        )


if __name__ == "__main__":
    main()