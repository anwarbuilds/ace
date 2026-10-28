"""Company-scoped evidence metadata, distinct from application outcomes.

Uses the existing email event ledger; no application is selected or changed.
"""
from __future__ import annotations

import json

KIND = "company_rejection"
COMPANY_REASON = "Company rejection recorded; the email does not need a role-level application match"


def encode_reason(company: str, explanation: str) -> str:
    return json.dumps({"scope": "company", "version": 1, "company": company,
                       "explanation": explanation}, sort_keys=True)


def event_company(event) -> str | None:
    if event.kind != KIND or event.actor != "verified_automation" or not event.gmail_message_id:
        return None
    if event.application_key != f"email:{event.gmail_message_id}":
        return None
    try:
        data = json.loads(event.reason)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    company = data.get("company")
    if (data.get("scope") != "company" or data.get("version") != 1
            or not isinstance(company, str) or not company.strip() or len(company) > 300):
        return None
    return company


def display_reason(event) -> str:
    company = event_company(event)
    return f"Rejection received from {company}; no individual application changed" if company else event.reason
