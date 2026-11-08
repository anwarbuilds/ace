"""Explicit role barriers differ from unknown or partially available sponsorship."""
import pytest
from backend.app.intelligence.eligibility import EligibilityReasonCode,EligibilityStatus,evaluate_job
from backend.app.models.job import CanonicalJob


def decide(text):
    return evaluate_job(CanonicalJob(source='test',company='Fictional Labs',external_id='blocker-wording',
        title='Data Engineer',location='Seattle, WA',
        description='Build Python and Go software services. Review code and document reliable APIs. '*6+'\n'+text,
        official_url='https://jobs.fictional.example/blocker-wording'))


@pytest.mark.parametrize('text',(
    'We are unable to provide visa sponsorship for this role.',
    'We cannot provide employment visa sponsorship for this position.',
    'We are unable to consider candidates who require visa sponsorship for this role.',
    'Candidates must work without visa sponsorship now or in the future.',
    'Candidates must not require visa sponsorship.',
    'We do not offer visa sponsorship or transfer for this position.',
    'No sponsorship offered for this position.',
    'This position is not available for any work sponsorship.',
    'Applicants must have work authorization that does not now or in the future require sponsorship of a visa.',
    'The employer is not offering relocation, sponsorship, and remote work options are not available.',
    'Sponsorship of new applicants for employment authorization, or other immigration-related support, is not available for this position.',
    'We will not provide immigration sponsorship for this role.',
))
def test_explicit_sponsorship_refusals_reject(text):
    assert EligibilityReasonCode.SPONSORSHIP_BLOCKER in decide(text).reason_codes


@pytest.mark.parametrize('text',(
    'Required Clearance: Secret\nRequired experience: 1 year.',
    'Build reliable models. Clearance: Must be eligible and willing to obtain a clearance.',
    'Clearance: Must be eligible to obtain a clearance.',
))
def test_explicit_clearance_fields_reject(text):
    assert EligibilityReasonCode.CLEARANCE_BLOCKER in decide(text).reason_codes


@pytest.mark.parametrize('text',(
    'We offer visa sponsorship for this role.',
    "We sponsor visas. We aren't able to successfully sponsor visas for every role and candidate.",
    'We cannot provide visa sponsorship for every role; sponsorship for this position is available.',
    'We are not able to provide visa sponsorship for all roles; ask recruiting about this opening.',
    'We offer sponsorship; relocation is not available.',
    'We are not offering relocation, but sponsorship is available.',
    'Sponsorship of new applicants for employment authorization is available, but relocation is not available.',
    'Sponsorship of new applicants for employment authorization may be available. Relocation is not available.',
    'We do not sponsor conference tickets. We offer visa sponsorship for this position.',
    'Required Clearance: None.',
    'Clearance: Not required.',
    'Complete an ordinary background check before starting.',
    'Background clearance: Must be eligible and willing to obtain a clearance. This is an ordinary background check.',
))
def test_positive_unknown_and_ordinary_background_cases_stay_eligible(text):
    assert decide(text).status is EligibilityStatus.PASS
