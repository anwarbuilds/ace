"""Fictional scoped screening facts, private Memory only, no real answers."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.answers.screening import screening_key, valid_screening_memory
from backend.tests.test_auth import fixture_client, fixture_factory, _pair  # Reuse isolated auth fixtures.

CASES = json.loads((Path(__file__).parent / 'fixtures/screening_memory.json').read_text())


@pytest.mark.parametrize('case', CASES)
def test_scoped_screening_catalog_has_exact_meaning_and_boundaries(case):
    expected = case['key']
    key = screening_key(case['question'])
    if expected and 'tenant:' in expected:
        assert key == expected.replace('fixture.example', '*')
    else:
        assert key == expected
    assert valid_screening_memory(case['question'], expected or 'fact:v1:unsupported', 'No', 'yesno', 'fixture.example') is bool(expected)
    if expected:
        assert not valid_screening_memory(case['question'], expected, 'Some other option', 'choice', 'fixture.example')
        assert not valid_screening_memory(case['question'], expected, 'No', 'text', 'fixture.example')
        assert not valid_screening_memory(case['question'], expected + ':different-scope', 'No', 'yesno', 'fixture.example')


def test_scoped_memory_uses_existing_private_resource_and_keeps_policy(client):
    token = _pair(client)
    extension = TestClient(client.app)
    headers = {'Authorization': 'Bearer ' + token}
    case = CASES[5]
    payload = dict(question=case['question'], concept=case['key'], answer='No', answer_type='yesno', source_host='fixture.example', reuse_policy='scoped')
    first = extension.put('/api/extension/memory', json=payload, headers=headers)
    assert first.status_code == 200
    again = extension.put('/api/extension/memory', json=payload, headers=headers)
    assert again.json()['id'] == first.json()['id'] and again.json()['revision'] == 1
    record = extension.get('/api/extension/memory', headers=headers).json()['items'][0]
    assert record['reuse_policy'] == 'scoped' and record['answer'] == 'No'
    changed = extension.put('/api/extension/memory', json={**payload, 'answer': 'Yes', 'expected_revision': 1}, headers=headers)
    assert changed.json()['revision'] == 2
    assert extension.put('/api/extension/memory', json={**payload, 'expected_revision': 1}, headers=headers).status_code == 409
    assert extension.put('/api/extension/memory', json={**payload, 'reuse_policy': 'reusable'}, headers=headers).status_code == 422
    assert client.get('/api/extension/memory').status_code == 200  # Owner from _pair.
    assert TestClient(client.app).get('/api/extension/memory').status_code == 401


def test_invalid_scoped_policy_cannot_bypass_protected_question_guard(client):
    token = _pair(client)
    extension = TestClient(client.app)
    headers = {'Authorization': 'Bearer ' + token}
    for question in ['Why do you want to join Fictional Labs?', 'Please sign this consent.', 'What is your gender?', 'Are you not a US citizen or permanent resident?']:
        payload = dict(question=question, concept='fact:v1:us-status:citizen,resident', answer='No', answer_type='yesno', reuse_policy='scoped')
        assert extension.put('/api/extension/memory', json=payload, headers=headers).status_code == 422
    assert extension.get('/api/extension/memory', headers=headers).json()['items'] == []


def test_learned_answers_store_protected_questions_but_never_motivation(client):
    token = _pair(client)
    extension = TestClient(client.app)
    headers = {'Authorization': 'Bearer ' + token}
    for concept, question, answer in [
        ('learn:bank:choice:need-sponsorship-in-future', 'Do you require any type of sponsorship now or in the future?', 'Yes'),
        ('learn:bank:choice:gender', 'Please select your gender.', 'Male'),
        ('learn:bank:choice:government-official-or-close-links', 'Are you currently a government official or do you have any close links to a government official?', 'No'),
        ('learn:topic:choice:continue-tick@fictional.wd5.myworkdayjobs.com/careers', 'Please select the tick box to continue.', 'Yes'),
    ]:
        saved = extension.put('/api/extension/memory', json=dict(concept=concept, question=question, answer=answer, answer_type='choice', source_host='fictional.example', reuse_policy='learned'), headers=headers)
        assert saved.status_code == 200, question
    items = extension.get('/api/extension/memory', headers=headers).json()['items']
    assert {item['reuse_policy'] for item in items} == {'learned'} and len(items) == 4
    update = extension.put('/api/extension/memory', json=dict(concept='learn:bank:choice:gender', question='What is your gender?', answer='Female', answer_type='choice', reuse_policy='learned', expected_revision=1), headers=headers)
    assert update.json()['revision'] == 2
    for concept, question in [
        ('learn:topic:text:join-silverpine', 'Why do you want to join Silverpine?'),
        ('learn:topic:text:full-name-signature', 'Electronic signature: type your full name'),
        ('q:sponsorship', 'Do you require sponsorship?'),
        ('fact:v1:us-status:citizen,resident', 'Are you a US citizen or permanent resident?'),
    ]:
        refused = extension.put('/api/extension/memory', json=dict(concept=concept, question=question, answer='No', answer_type='choice', reuse_policy='learned'), headers=headers)
        assert refused.status_code == 422, question
    reusable = extension.put('/api/extension/memory', json=dict(concept='learn:bank:choice:gender', question='Please select your gender.', answer='Male', answer_type='choice', reuse_policy='reusable'), headers=headers)
    assert reusable.status_code == 422, 'the learn: namespace never enters the routine policy'
    assert len(extension.get('/api/extension/memory', headers=headers).json()['items']) == 4
