"""Safety properties of the Gmail matcher, using fictional records only."""

from datetime import datetime, timedelta, timezone

from backend.app.inbox.reconcile import ApplicationIdentity, EmailEvidence, reconcile
from backend.app.inbox import gmail
from backend.app.api.routers.inbox import _message_evidence


NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)


def app(key: str, req: str, status: str = "applied") -> ApplicationIdentity:
    return ApplicationIdentity(key, "Silverpine Labs", "Software Engineer", req, NOW - timedelta(days=30), status, "https://careers.silverpine.example/jobs")


def mail(body: str, sender: str = "talent@careers.silverpine.example") -> EmailEvidence:
    return EmailEvidence(sender, "Application update", body, NOW, True)


def test_ambiguous_rejection_protects_every_pending_application():
    apps = [app("job:1", "SE-101"), app("job:2", "SE-102"), app("job:3", "SE-103")]
    result = reconcile(mail("We have decided to move forward with other candidates."), apps)
    assert result.disposition == "review"
    assert result.target is None
    assert result.candidates == ("job:1", "job:2", "job:3")
    assert all(a.current_status == "applied" for a in apps)


def test_exact_unique_rejection_can_be_verified_without_touching_other_applications():
    apps = [app("job:1", "SE-101"), app("job:2", "SE-102"), app("job:3", "SE-103")]
    result = reconcile(mail("Requisition: SE-102. We have decided to move forward with other candidates."), apps)
    assert result.disposition == "verified"
    assert result.target == "job:2"


def test_reused_identifier_and_untrusted_sender_never_verify():
    evidence = mail("Req ID: SE-102. You have not been selected.")
    assert reconcile(evidence, [app("job:1", "SE-102"), app("job:2", "SE-102")]).target is None
    assert reconcile(mail(evidence.body, "recruiter@gmail.com"), [app("job:1", "SE-102")]).target is None


def test_old_message_and_terminal_status_never_verify():
    old = EmailEvidence("talent@careers.silverpine.example", "Update", "Req ID: SE-102. You have not been selected.", NOW - timedelta(days=60), True)
    assert reconcile(old, [app("job:1", "SE-102")]).target is None
    assert reconcile(mail(old.body), [app("job:1", "SE-102", "accepted")]).target is None
    corrected = ApplicationIdentity("job:1", "Silverpine Labs", "Software Engineer", "SE-102", NOW-timedelta(days=90), "screening", "https://careers.silverpine.example/jobs", NOW-timedelta(days=1))
    assert reconcile(old, [corrected]).target is None


def test_forwarded_rejection_does_not_supply_outcome_intent():
    evidence = mail("FYI, see below.\n----- Forwarded message -----\nReq ID: SE-102. You have not been selected.")
    assert reconcile(evidence, [app("job:1", "SE-102")]).target is None


def test_visible_from_without_gmail_dmarc_result_cannot_verify():
    evidence = EmailEvidence("talent@careers.silverpine.example", "Update", "Req ID: SE-102. You have not been selected.", NOW)
    assert reconcile(evidence, [app("job:1", "SE-102")]).target is None


def test_forwarded_subject_does_not_supply_rejection_intent():
    evidence = EmailEvidence("talent@careers.silverpine.example", "Fwd: Req ID: SE-102. You have not been selected.", "FYI", NOW, True)
    assert reconcile(evidence, [app("job:1", "SE-102")]).target is None


def test_gmail_authentication_result_must_align_with_visible_sender():
    base = {"internalDate": str(int(NOW.timestamp() * 1000)), "payload": {"headers": [
        {"name": "From", "value": "talent@careers.silverpine.example"},
        {"name": "Subject", "value": "Application update"},
    ]}, "snippet": "Req ID: SE-102. You have not been selected."}
    assert not _message_evidence(base).sender_authenticated
    base["payload"]["headers"].insert(0, {"name": "Authentication-Results", "value": "mx.google.com; dmarc=pass header.from=attacker.example"})
    assert not _message_evidence(base).sender_authenticated
    base["payload"]["headers"][0]["value"] = "mx.google.com; dmarc=pass header.from=careers.silverpine.example"
    evidence = _message_evidence(base)
    assert evidence.sender_authenticated
    assert reconcile(evidence, [app("job:1", "SE-102")]).target == "job:1"


def test_gmail_grant_uses_read_only_scope_pkce_and_encrypted_refresh_token():
    from cryptography.fernet import Fernet
    verifier, challenge = gmail.pkce_pair()
    url = gmail.authorization_url("fictional-client", "https://ace.example.test/api/inbox/google/callback", "state", "nonce", challenge)
    assert "gmail.readonly" in url and "code_challenge_method=S256" in url
    assert "gmail.modify" not in url and "gmail.send" not in url
    assert verifier not in url
    key = Fernet.generate_key().decode()
    stored = gmail.encrypt_token("fictional-refresh-token", key)
    assert b"fictional-refresh-token" not in stored
    assert gmail.decrypt_token(stored, key) == "fictional-refresh-token"
