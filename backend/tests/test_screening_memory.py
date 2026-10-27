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
