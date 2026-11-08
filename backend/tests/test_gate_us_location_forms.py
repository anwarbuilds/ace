"""Compressed US locations keep explicit foreign-country guards."""

import pytest

from backend.app.intelligence.eligibility import (
    EligibilityReasonCode,
    EligibilityStatus,
    _is_us_location,
    evaluate_job,
)
from backend.app.models.job import CanonicalJob


@pytest.mark.parametrize("location", (
    "Tallahassee FL + 1 more", "Tallahassee FL", "  Tallahassee FL + 12 more  ",
    "Cambridge MA + 2 more", "Richmond VA + 1 more", "Wilmington DE + 3 more",
    "Bloomington IN + 1 more", "Springfield IL + 2 more", "Boise ID + 1 more",
    "Ontario CA + 1 more", "Vancouver WA + 2 more", "St. Louis MO + 1 more",
    "Coeur d'Alene ID + 1 more", "Any State", " any state ", "ANY STATE",
))
def test_compressed_us_locations_are_recognized(location):
    assert _is_us_location(location)


@pytest.mark.parametrize("location", (
    "Tallahassee FL + 1 more, India", "Any State, Canada", "Any State, Australia",
    "Toronto ON + 1 more", "Toronto ON CA + 1 more", "Vancouver BC CA + 2 more",
    "Toronto on CA + 1 more", "Berlin be DE + 1 more",
    "Berlin BE DE + 1 more", "Bengaluru KA IN + 1 more", "Pune IN + 1 more",
    "Chennai TN IND + 1 more", "San Jose CA + 1 more, Costa Rica",
    "Cambridge MA + 1 more, United Kingdom", "London England + 1 more",
    "work in", "remote or", "Any State worldwide", "IN", "FL", "CA",
))
def test_foreign_or_unsupported_text_does_not_become_a_us_address(location):
    assert not _is_us_location(location)


@pytest.mark.parametrize("location", (
    "US / Canada", "Remote, Canada; Remote, US", "Toronto, Canada; United States",
    "Austin, TX", "Evansville, IN", "Ontario, CA",
))
def test_existing_explicit_us_and_mixed_country_locations_stay_recognized(location):
    assert _is_us_location(location)


def test_the_normal_gate_uses_the_new_location_shape():
    job = CanonicalJob(
        source="test", company="Fictional Labs", external_id="compressed-location",
        title="Software Engineer", location="Tallahassee FL + 1 more",
        description="Build software in Python and Go. This is a full-time position. "
        "Review code, design services and document changes with our engineering team. "
        "Requires 2 years of professional software development experience. " * 2,
        official_url="https://jobs.fictional.example/compressed-location",
    )
    decision = evaluate_job(job)
    assert decision.status is EligibilityStatus.PASS
    assert EligibilityReasonCode.OUTSIDE_US not in decision.reason_codes
