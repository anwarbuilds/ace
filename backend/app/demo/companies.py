"""Fictional employers for the demo database.

The repository is public, so the demo (``backend/scripts/seed_demo.py``)
names no real company. These names are invented. Each carries the tier
it should display under, so a demo queue shows every tier, its rail and
its badge, the way a real one does.

The tier lists in ``backend.app.intelligence.companies`` only take these
in when ``ACE_DEMO_COMPANIES=1`` is set, so a real deployment can never
rank an employer by a demo name that happens to collide with it.
"""

from __future__ import annotations


DEMO_COMPANY_TIERS: dict[str, str] = {
    "Quorvane": "BIG_TECH",
    "Halcyra": "BIG_TECH",
    "Zentrix": "BIG_TECH",
    "Omnivale": "BIG_TECH",
    "Strataloom": "BIG_TECH",
    "Kestrel Grid": "TOP_TIER",
    "Marlowe Robotics": "TOP_TIER",
    "Pinecrest AI": "TOP_TIER",
    "Lumora Pay": "TOP_TIER",
    "Tessellate": "TOP_TIER",
    "Ferrovia": "TOP_TIER",
    "Brightmoor Health": "TOP_TIER",
    "Cindervale": "TOP_TIER",
    "Arborwave": "ESTABLISHED",
    "Quillfeather": "ESTABLISHED",
    "Driftmark": "ESTABLISHED",
    "Saltbridge Insurance": "ESTABLISHED",
    "Ironleaf Logistics": "ESTABLISHED",
    "Copperfield Media": "ESTABLISHED",
    "Granite Ledger": "ESTABLISHED",
    "Wrenfield": "OTHER",
    "Lanternfish": "OTHER",
    "Oakhollow": "OTHER",
    "Glimmerline": "OTHER",
    "Pebblecrest": "OTHER",
    "Sundial Bio": "OTHER",
    "Verdance Energy": "OTHER",
    "Hollowbrook": "OTHER",
    "Nimbleroot": "OTHER",
    "Starling Ferry": "OTHER",
}


def demo_names_for(
    tier: str,
) -> frozenset[str]:
    """Return the lowercase demo names in one tier."""

    return frozenset(
        name.lower()
        for name, value in DEMO_COMPANY_TIERS.items()
        if value == tier
    )
