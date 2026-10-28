"""Fictional Gmail authentication assertions; no DNS or provider calls."""
import pytest

from backend.app.api.routers.inbox import _authenticated_sender


def headers(value):
    return [{'name':'Authentication-Results','value':value}]


@pytest.mark.parametrize('signer', ['header.i=@careers.silverpine.example','header.d=careers.silverpine.example','header.i=@silverpine.example'])
def test_google_parent_domain_pass_with_aligned_dkim_authenticates_subdomain(signer):
    assert _authenticated_sender(headers('mx.google.com; dkim=pass '+signer+'; dmarc=pass header.from=silverpine.example'),'careers.silverpine.example')


@pytest.mark.parametrize('value', [
    'mx.google.com; dkim=pass header.i=@silverpine.example; dmarc=fail header.from=silverpine.example',
    'mx.google.com; dkim=pass header.i=@silverpine.example; dmarc=fail header.from=silverpine.example; dmarc=pass header.from=silverpine.example',
    'mx.google.com; dkim=pass header.i=@mailvendor.example; dmarc=pass header.from=silverpine.example',
    'mx.google.com; spf=pass smtp.mailfrom=silverpine.example; dmarc=pass header.from=silverpine.example',
    'mx.google.com; dkim=pass header.i=@silverpine.example',
    'mx.google.com; dkim=pass header.i=@silverpine.example; dmarc=none header.from=silverpine.example',
    'mx.google.com; arc=pass (dkim=pass header.i=@silverpine.example dmarc=pass header.from=silverpine.example)',
    'mx.google.com; dkim=fail header.i=@silverpine.example; dmarc=pass header.from=silverpine.example',
    'mx.google.com; dkim=pass header.i=@careers.silverpine.example.attacker.test; dmarc=pass header.from=silverpine.example',
])
def test_parent_domain_without_aligned_evidence_or_explicit_failure_is_blocked(value):
    assert not _authenticated_sender(headers(value),'careers.silverpine.example')


def test_sibling_and_lookalike_domains_are_not_parent_alignment():
    value='mx.google.com; dkim=pass header.i=@silverpine.example; dmarc=pass header.from=silverpine.example'
    for sender in ['silverpine.example.attacker.test','notsilverpine.example','silverpine-other.example']:
        assert not _authenticated_sender(headers(value),sender)


def test_exact_google_pass_keeps_existing_behavior():
    assert _authenticated_sender(headers('mx.google.com; dmarc=pass header.from=silverpine.example'),'silverpine.example')


def test_other_auth_servers_and_later_forged_google_results_are_not_used():
    good='mx.google.com; dkim=pass header.i=@silverpine.example; dmarc=pass header.from=silverpine.example'
    assert not _authenticated_sender(headers(good.replace('mx.google.com','untrusted.example')),'careers.silverpine.example')
    assert not _authenticated_sender(headers('mx.google.com; dmarc=fail header.from=silverpine.example')+headers(good),'careers.silverpine.example')
