"""Markers for recognized email meaning without an application outcome.

Persist the existing ``update`` decision for API rollback compatibility. These
markers are written only after complete, authenticated current-body reading;
the shared queue projection exposes the evidence states without a migration.
"""

REJECTION_PREFIX = "Classified rejection evidence; no application was changed. "
ACTION_PREFIX = "Classified hiring action; no application was changed. "
DECISIONS = frozenset({'classified_rejection', 'classified_action'})
ACTION_KINDS = frozenset({'online_assessment', 'interview', 'offer', 'recruiter_reply', 'action_required'})

# Earlier explicitly approved, complete authenticated action corrections were
# filed with these exact reasons. Keep their recognized progress visible
# without rewriting the stored mail or replaying an application stage.
LEGACY_ACTION_REASONS = {
    'online_assessment': 'Historical assessment reminder; filed as email evidence without changing application status or linkage.',
    'interview': 'Historical interview schedule; filed as email evidence without changing application status or linkage.',
}
