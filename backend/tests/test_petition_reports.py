import pytest

from backend.scripts.import_petition_reports import checked_row


def sample():
    return {"ace_company": "Fictional Research", "legal_entity": "Fictional Research Inc",
            "period": "FY 2025", "report_version": "2025-q4", "approvals": "12", "denials": "3",
            "source_uri": "https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub",
            "entity_reviewed": "yes"}


def test_reviewed_uscis_decisions_are_kept_distinct_from_hiring_rate():
    row = checked_row(sample())
    assert row["metric_definition"] == "USCIS I-129 petition decisions"
    assert row["petition_approvals"] == 12
    assert "hiring_sponsorship_rate" not in row


@pytest.mark.parametrize("edit", [
    {"source_uri": "https://not-uscis.example/data"},
    {"entity_reviewed": "no"},
    {"period": "today"},
    {"approvals": "-1"},
])
def test_unverified_or_invalid_evidence_is_rejected(edit):
    with pytest.raises(ValueError):
        checked_row({**sample(), **edit})
