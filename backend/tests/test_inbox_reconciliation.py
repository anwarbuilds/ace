"""Safety properties of the Gmail matcher, using fictional records only."""

import base64

from datetime import datetime, timedelta, timezone

from backend.app.inbox.reconcile import ApplicationIdentity, EmailEvidence, reconcile
from backend.app.inbox import gmail
from backend.app.api.routers.inbox import _message_evidence
from backend.app.inbox.company_outcomes import KIND, COMPANY_REASON


NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)


def app(key: str, req: str, status: str = "applied") -> ApplicationIdentity:
    return ApplicationIdentity(key, "Silverpine Labs", "Software Engineer", req, NOW - timedelta(days=30), status, "https://careers.silverpine.example/jobs")


def mail(body: str, sender: str = "talent@careers.silverpine.example") -> EmailEvidence:
    return EmailEvidence(sender, "Application update", body, NOW, True)


def test_ambiguous_rejection_protects_every_pending_application():
    apps = [app("job:1", "SE-101"), app("job:2", "SE-102"), app("job:3", "SE-103")]
    result = reconcile(mail("We have decided to move forward with other candidates."), apps)
    assert result.disposition == KIND and result.company == "Silverpine Labs"
    assert result.target is result.matched_target is None
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
    partial = reconcile(evidence, [app("job:1", "SE-102")])
    assert partial.disposition == "review" and partial.reason == "Only part of this email could be read"
    base["payload"].update({"mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(base["snippet"].encode()).decode()}})
    assert reconcile(_message_evidence(base), [app("job:1", "SE-102")]).target == "job:1"


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


# Owner decision 2026-10-26: clear rejections are recorded automatically when
# exactly one application fits; everything uncertain stays in review.

import base64

import pytest

from backend.app.inbox.reconcile import classify


def ats_mail(subject: str, body: str, display: str = "Northwind Robotics", address: str = "no-reply@us.greenhouse-mail.io",
             received: datetime = NOW, authenticated: bool = True) -> EmailEvidence:
    return EmailEvidence(f"{display} <{address}>", subject, body, received, authenticated)


def northwind(key: str = "job:7", title: str = "Software Engineer, New Grad", req: str | None = None,
              status: str = "applied", submitted: datetime = NOW - timedelta(days=12)) -> ApplicationIdentity:
    return ApplicationIdentity(key, "Northwind Robotics, Inc.", title, req, submitted, status, "https://boards.greenhouse.io/northwind")


@pytest.mark.parametrize("sentence", [
    "Unfortunately, we won't be moving forward with your application.",
    "We have decided to pursue other candidates for this role.",
    "We are not able to move forward with your application at this time.",
    "The position you applied for has been filled.",
    "After careful consideration, we've decided to move forward with another candidate.",
    "Your application was not successful on this occasion.",
    "We regret to inform you that the team chose another path for this position.",
    "We have decided to go in a different direction for this role.",
    "We have moved forward with other applicants whose experience fits more closely.",
])
def test_common_rejection_wording_is_recognized(sentence):
    assert classify(ats_mail("Your application", sentence))[0] == "rejection"


@pytest.mark.parametrize("sentence,expected", [
    ("We understand you have decided not to proceed with your application.", "unknown"),
    ("We are continuing to interview other candidates and will update you soon about the role.", "unknown"),
    ("Thank you for applying! We have received your application.", "application_confirmation"),
])
def test_withdrawals_updates_and_receipts_are_not_rejections(sentence, expected):
    assert classify(ats_mail("Your application", sentence))[0] == expected


def test_reference_label_counts_as_a_job_id():
    apps = [northwind(req="137787"), northwind("job:8", "Software Engineer, Platform", "137790")]
    result = reconcile(ats_mail("Update", "Ref: 137787. We have decided to move forward with other candidates."), apps)
    assert (result.disposition, result.target) == ("verified", "job:7")
    assert result.reason == "Clear rejection matched by its job ID"


def test_only_application_at_the_named_company_is_matched():
    result = reconcile(ats_mail("Thank you for your interest in Northwind Robotics",
                                "Thank you for applying for the Software Engineer role. Unfortunately, we will not be moving forward."),
                       [northwind(), ApplicationIdentity("job:9", "Bluefin Analytics", "Software Engineer", None, NOW - timedelta(days=3), "applied")])
    assert (result.disposition, result.target) == ("verified", "job:7")
    assert result.reason == "Clear rejection matched by your only application there"


def test_a_different_role_records_company_evidence_without_selecting_the_likely_application():
    result = reconcile(ats_mail("Northwind Robotics application update",
                                "Thank you for applying for the Data Analyst position. We regret to inform you that it has been filled."),
                       [northwind()])
    assert result.disposition == KIND and result.target is result.matched_target is None
    assert result.company == "Northwind Robotics, Inc."
    assert result.candidates == ("job:7",)


def test_exact_title_picks_one_of_several_applications():
    apps = [northwind(), northwind("job:8", "Machine Learning Engineer")]
    result = reconcile(ats_mail("Northwind Robotics", "About your Machine Learning Engineer application: you have not been selected."), apps)
    assert (result.disposition, result.target) == ("verified", "job:8")
    generic = reconcile(ats_mail("Northwind Robotics", "We regret to inform you that we will not be moving forward with your application."), apps)
    assert generic.disposition == KIND and set(generic.candidates) == {"job:7", "job:8"}
    assert generic.company == "Northwind Robotics, Inc." and generic.target is generic.matched_target is None


def test_rejection_rules_keep_their_protections():
    body = "We regret to inform you that we will not be moving forward with your application."
    personal = reconcile(ats_mail("Northwind Robotics", body, address="recruiter@gmail.com"), [northwind()])
    assert personal.disposition == "review" and personal.reason == "Sender could not be authenticated"
    unauthenticated = reconcile(ats_mail("Northwind Robotics", body, authenticated=False), [northwind()])
    assert unauthenticated.target is None
    accepted_app = northwind(status="accepted")
    accepted = reconcile(ats_mail("Northwind Robotics", body), [accepted_app])
    assert accepted.reason == COMPANY_REASON and accepted.company == accepted_app.company
    assert accepted.disposition == KIND and accepted.target is accepted.matched_target is None
    assert accepted_app.current_status == 'accepted'


def test_marking_applied_after_a_quick_rejection_still_matches():
    early = reconcile(ats_mail("Northwind Robotics", "You have not been selected for this role.", received=NOW - timedelta(hours=2)),
                      [ApplicationIdentity("job:7", "Northwind Robotics", "Software Engineer", None, NOW, "applied", None, NOW)])
    assert early.disposition == "verified"


def test_an_already_rejected_application_gets_the_email_date():
    result = reconcile(ats_mail("Northwind Robotics", "We have decided to pursue other candidates for this role."),
                       [ApplicationIdentity("job:7", "Northwind Robotics", "Software Engineer", None, NOW - timedelta(days=9), "rejected", None, NOW)])
    assert (result.disposition, result.target) == ("verified", "job:7")


def test_positive_outcomes_from_a_shared_platform_still_need_the_owner():
    result = reconcile(ats_mail("Northwind Robotics interview", "Job ID 137787. We would like to invite you to interview."),
                       [northwind(req="137787")])
    assert result.disposition == "review" and result.candidates[0] == "job:7"


def test_receipts_are_filed_and_years_are_not_job_ids():
    receipt = reconcile(ats_mail("Northwind Robotics", "Thank you for applying to the 2026 Software Engineer, New Grad role."),
                        [northwind(req="2026")])
    assert receipt.disposition == "receipt"
    assert receipt.requisition_id is None


def test_html_only_email_is_read_as_text():
    markup = ("<html><head><style>p{color:red}</style></head><body><p>Hello,</p><p>Thank you for applying to Northwind Robotics."
              "</p><div>Unfortunately, we&rsquo;ve decided to move forward with other candidates.</div><script>alert(1)</script></body></html>")
    data = {"internalDate": str(int(NOW.timestamp() * 1000)), "snippet": "Hello, Thank you for applying",
            "payload": {"mimeType": "multipart/alternative", "headers": [
                {"name": "Authentication-Results", "value": "mx.google.com; dmarc=pass header.from=us.greenhouse-mail.io"},
                {"name": "From", "value": "Northwind Robotics <no-reply@us.greenhouse-mail.io>"},
                {"name": "Subject", "value": "Your application"}],
                "parts": [{"mimeType": "text/html", "headers": [{"name": "Content-Type", "value": 'text/html; charset="utf-8"'}],
                           "body": {"data": base64.urlsafe_b64encode(markup.encode()).decode()}}]}}
    evidence = _message_evidence(data)
    assert "alert" not in evidence.body and "color" not in evidence.body
    assert "we’ve decided to move forward with other candidates" in evidence.body
    assert reconcile(evidence, [northwind()]).target == "job:7"


# Parser version 3 (2026-10-26): a rejection that opens with thanks must
# reach the owner, never sit among receipts.

import dataclasses


def test_rejection_that_opens_with_thanks_from_a_shared_platform_is_recorded():
    body = ("Hi Fixture,\n\nThank you for applying for the Full-Stack Software Engineer role at Wayfern, we know applying "
            "takes real effort.\n\nWe’ve reviewed your application in detail, and on this occasion we won’t be "
            "moving forward.\n\nBest,\nWayfern Talent Team")
    evidence = ats_mail("Update on your application at Wayfern - Full-Stack Software Engineer", body,
                        display="Wayfern London Engineering", address="no-reply@ashbyhq.com")
    wayfern = [ApplicationIdentity(f"job:{n}", "wayfern", title, None, NOW - timedelta(days=4), "applied")
               for n, title in ((1, "Full-Stack Software Engineer"), (2, "Machine Learning Engineer"), (3, "Software Engineer, Simulation"))]
    result = reconcile(evidence, wayfern)
    assert (result.classification, result.disposition, result.target) == ("rejection", "verified", "job:1")
    assert result.reason == "Clear rejection matched by its exact title"
    # The same role applied to twice produces company evidence, without an
    # application choice or an instruction to change both applications.
    twice = reconcile(evidence, wayfern + [ApplicationIdentity("job:4", "wayfern", "Full-Stack Software Engineer", None, NOW - timedelta(days=2), "applied")])
    assert twice.disposition == KIND and twice.company == 'wayfern'
    assert twice.target is twice.matched_target is None
    assert set(twice.candidates) == {"job:1", "job:2", "job:3", "job:4"}


@pytest.mark.parametrize("sentence", [
    "Unfortunately, we have decided to move ahead with other candidates.",
    "We won't be able to offer you a position at this time.",
    "We regret that we cannot offer you this role.",
    "Your application was not selected for the next stage.",
    "The position is no longer available.",
    "We have chosen to pursue other candidates at this time.",
    "We have decided to pursue other candidates who align more closely with the role requirements.",
    "After review, the team has chosen to pursue another candidate for this position.",
])
def test_more_rejection_wording_is_recognized(sentence):
    assert classify(ats_mail("Your application", "Thank you for applying. " + sentence))[0] == "rejection"


def test_receipt_with_delay_and_other_candidates_still_under_review_is_not_a_rejection():
    result = reconcile(ats_mail("Northwind Robotics", "Thank you for applying. We regret the delay; other candidates are still being reviewed."),
                       [northwind()])
    assert (result.classification, result.disposition, result.target) == ("application_confirmation", "receipt", "job:7")
    assert result.candidates == ("job:7",)


def test_a_receipt_read_only_from_the_snippet_waits():
    partial = EmailEvidence("Northwind Robotics <no-reply@us.greenhouse-mail.io>", "Northwind Robotics",
                            "Thank you for applying to Northwind Robotics. We have reviewed", NOW, True, complete=False)
    result = reconcile(partial, [northwind()])
    assert (result.disposition, result.reason) == ("review", "Only part of this email could be read")
    assert reconcile(dataclasses.replace(partial, complete=True), [northwind()]).disposition == "receipt"


def test_html_with_an_unclosed_head_is_still_read():
    markup = ("<html><head><meta charset='utf-8'><style>p{color:red}</style><body><p>Thank you for applying to Northwind Robotics."
              "</p><p>Unfortunately, we won't be moving forward.</p></body></html>")
    data = {"internalDate": str(int(NOW.timestamp() * 1000)), "snippet": "Thank you for applying",
            "payload": {"mimeType": "text/html", "headers": [{"name": "From", "value": "Northwind Robotics <no-reply@us.greenhouse-mail.io>"},
                                                             {"name": "Subject", "value": "Your application"}],
                        "body": {"data": base64.urlsafe_b64encode(markup.encode()).decode()}}}
    evidence = _message_evidence(data)
    assert evidence.complete and "won't be moving forward" in evidence.body
    assert classify(evidence)[0] == "rejection"


def test_a_workday_tenant_names_the_employer():
    gm = [ApplicationIdentity("job:21", "General Motors", "Software Engineer", None, NOW - timedelta(days=5), "applied"),
          ApplicationIdentity("job:22", "Fictional Labs", "Software Engineer", None, NOW - timedelta(days=5), "applied")]
    evidence = EmailEvidence("generalmotors@myworkday.com", "Your interest in Software Engineer at GM",
                             "Thank you for applying. Unfortunately, we have decided to pursue other candidates.", NOW, True)
    result = reconcile(evidence, gm)
    assert (result.disposition, result.target) == ("verified", "job:21")
    # Other platforms still never name an employer by their address.
    other = reconcile(EmailEvidence("generalmotors@us.greenhouse-mail.io", evidence.subject, evidence.body, NOW, True), gm)
    assert other.target is None


def test_a_workday_tenant_made_of_initials_names_the_employer():
    apps = [ApplicationIdentity("job:31", "Cambridge Investment Research", "Full Stack Software Engineer", None, NOW - timedelta(days=12), "applied"),
            ApplicationIdentity("job:32", "Fictional Labs", "Full Stack Software Engineer", None, NOW - timedelta(days=12), "applied")]
    body = ("Thank you for your interest in a role with Cambridge. After reviewing your application for the Full Stack Software "
            "Engineer, we've made the decision to move forward with other candidates at this time.")
    result = reconcile(EmailEvidence("cir@myworkday.com", "Thank you for your interest!", body, NOW, True), apps)
    assert (result.classification, result.disposition, result.target) == ("rejection", "verified", "job:31")


@pytest.mark.parametrize("sentence", [
    "We cannot proceed with your application because our immigration policy does not include sponsorship for this role.",
    "Your application is declined because we are unable to sponsor for this position.",
    "You are not eligible for this position.",
    "Your application does not meet the requirements.",
    "We have decided not to proceed with your application for this role.",
    "We will not be considering your application.",
    "Your candidacy was not selected for this role.",
    "We are not able to offer a position at this time.",
])
def test_parser_six_sponsorship_and_eligibility_rejections(sentence):
    assert classify(ats_mail("Your application", sentence))[0] == "rejection"
    assert reconcile(ats_mail("Northwind Robotics application", sentence), [northwind()]).disposition == "verified"


def test_fictional_workday_sponsorship_rejection_retains_ambiguity_auth_and_final_guards():
    application = ApplicationIdentity("job:88", "Fictional Mac", "Software Engineer Professional", None, NOW-timedelta(days=10), "applied")
    evidence = EmailEvidence("Workday <fictionalmac@myworkday.com>", "Fictional Mac - Application Update",
        "Thank you for your interest in the Software Engineer Professional position. We would like to inform you that Fictional Mac's immigration policy does not include sponsorship for this role and does not hire students or F-1 graduates. We cannot proceed with your application.", NOW, True)
    assert reconcile(evidence, [application]).target == "job:88"
    assert reconcile(evidence, [application, dataclasses.replace(application, key="job:89")]).target is None
    assert reconcile(dataclasses.replace(evidence, sender_authenticated=False), [application]).target is None
    for status in ["accepted", "withdrawn", "offer"]:
        assert reconcile(evidence, [dataclasses.replace(application, current_status=status)]).target is None


@pytest.mark.parametrize("evidence", [
    ats_mail("Application message", "Please check the candidate portal.", display="Talent", address="fictional@myworkday.com"),
    ats_mail("Your application", "There is another update about your Software Engineer role.", display="Talent", address="talent@fictional.example"),
    ats_mail("Northwind Robotics application", "An update is available.", display="Talent", address="talent@fictional.example"),
])
def test_unclear_application_email_is_saved_without_a_manual_task(evidence):
    result = reconcile(evidence, [northwind()])
    assert (result.classification, result.disposition, result.target) == ("unclear", "update", None)
    assert "Saved application correspondence" in result.reason


@pytest.mark.parametrize("domain", ["linkedin.com", "mail.indeed.com", "joinhandshake.com", "glassdoor.com", "ziprecruiter.com"])
def test_job_board_unknown_mail_does_not_enter_safety_net(domain):
    evidence = ats_mail("Application jobs you may like", "New Software Engineer positions match your interests.", address="news@"+domain)
    assert reconcile(evidence, [northwind()]).disposition == "ignored"


def test_non_application_and_self_sent_mail_do_not_change_applications():
    assert reconcile(ats_mail("News", "A fictional newsletter."), [northwind()]).disposition == "ignored"
    evidence = mail("Req ID: SE-102. You have not been selected.", "Owner <owner@example.test>")
    assert reconcile(evidence, [app("job:1", "SE-102")], account="OWNER@example.test").disposition == "ignored"
    assert classify(EmailEvidence("fictional@example.test", "Bank update", "You are not eligible for a loan.", NOW))[0] == "unknown"


@pytest.mark.parametrize("sentence", [
    "If you are not eligible for this role, please withdraw your application.",
    "Please check whether your application does not meet the requirements.",
    "A delay does not mean you are not eligible for this position.",
])
def test_conditional_eligibility_wording_never_automates_a_rejection(sentence):
    result = reconcile(ats_mail("Northwind Robotics application", sentence), [northwind()])
    assert result.disposition == "update" and result.target is None


@pytest.mark.parametrize("status,classification,body", [
    ("offer","interview","Req ID: SE-102. We invite you to interview."),
    ("interviewing","online_assessment","Req ID: SE-102. Complete the online assessment."),
    ("offer","online_assessment","Req ID: SE-102. Complete the online assessment."),
])
def test_automatic_positive_outcome_cannot_regress_a_later_stage(status,classification,body):
    result=reconcile(mail(body),[app("job:1","SE-102",status)])
    assert result.classification==classification and result.disposition=="review"
    assert result.reason=="Existing later application stage is protected"
