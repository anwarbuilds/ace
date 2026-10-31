"""The reconciliation detects evidence omitted from otherwise consistent totals."""
from scripts import audit_analytics_inbox_sync as sync_audit
from backend.tests.test_analytics_inbox_sync import pipeline, ingest
from backend.tests.test_analytics_read import db, NOW


def test_read_only_audit_reconciles_effective_categories_and_detects_an_omission(pipeline, monkeypatch):
    session, _, _ = pipeline
    ingest(pipeline, "receipt-audit", "Thank you for applying. We received your application.")
    ingest(pipeline, "interview-audit", "Please book your technical interview.", unknown_employer=True)
    checked = sync_audit.audit(session, now=NOW)
    assert checked["all_checks_pass"]
    assert checked["gmail_calls"] == checked["body_reads"] == checked["writes"] == 0

    real_read = sync_audit.analytics_read

    def omitted(*args, **kwargs):
        result = real_read(*args, **kwargs)
        result["classified_email_evidence"]["categories"]["interview"] = 0
        return result

    monkeypatch.setattr(sync_audit, "analytics_read", omitted)
    broken = sync_audit.audit(session, now=NOW)
    assert not broken["all_checks_pass"]
    assert all(not row["checks"]["effective_email_categories"] for row in broken["ranges"].values())
