"""Privacy-safe metrics over explicit reference labels, never inferred labels.

Callers keep message text and real identities outside this aggregate result.
Unknown denominators stay null. Owner filings are policy decisions, not gold
semantic labels; the evaluator does not silently convert them into labels.
"""
from collections import Counter
from math import sqrt


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _wilson(successes, total):
    if not total:
        return None
    z = 1.96
    p = successes / total
    denominator = 1 + z*z/total
    middle = (p + z*z/(2*total))/denominator
    half = z*sqrt(p*(1-p)/total+z*z/(4*total*total))/denominator
    return [max(0, middle-half), min(1, middle+half)]


def evaluate(examples: list[dict]) -> dict:
    labelled = [row for row in examples if row.get('expected_classification') is not None]
    cells = Counter((r['expected_classification'], r['classification']) for r in labelled)
    categories = sorted({kind for pair in cells for kind in pair})
    per_category = {}
    for kind in categories:
        actual = sum(n for (expected, _), n in cells.items() if expected == kind)
        predicted = sum(n for (_, found), n in cells.items() if found == kind)
        correct = cells[kind, kind]
        per_category[kind] = {'support': actual, 'predicted': predicted,
                              'precision': _ratio(correct, predicted), 'recall': _ratio(correct, actual),
                              'recall_95pct_wilson': _wilson(correct, actual)}
    matched = [r for r in examples if 'expected_target' in r]
    false_rejection = sum(r['classification']=='rejection' and r['expected_classification']!='rejection' for r in labelled)
    false_auto_rejection = sum(r['classification']=='rejection' and r['expected_classification']!='rejection'
                               and (r.get('would_record_outcome',False) or r.get('would_change_status',False)) for r in labelled)
    wrong_update = sum((r.get('would_record_outcome',False) or r.get('would_change_status',False)) and r.get('target')!=r['expected_target'] for r in matched)
    return {'labelled': len(labelled), 'unlabelled': len(examples)-len(labelled), 'per_category': per_category,
            'confusion_matrix': {actual:{predicted:cells[actual,predicted] for predicted in categories} for actual in categories},
            'false_rejections': false_rejection,
            'non_rejection_reference_support':sum(r['expected_classification']!='rejection' for r in labelled),
            'false_rejection_rate':_ratio(false_rejection,sum(r['expected_classification']!='rejection' for r in labelled)),
            'missed_rejections': sum(r['expected_classification']=='rejection' and r['classification']!='rejection' for r in labelled),
            'false_automatic_rejections': false_auto_rejection, 'wrong_application_updates': wrong_update,
            'matching_labelled':len(matched),
            'review_labelled':sum('expected_review' in r for r in examples),
            'unnecessary_review_rate':_ratio(sum(r.get('review_required',False) and not r['expected_review'] for r in examples if 'expected_review' in r),sum(not r['expected_review'] for r in examples if 'expected_review' in r)),
            'matching_accuracy':_ratio(sum(r.get('target')==r['expected_target'] for r in matched),len(matched)),
            'release_blocking_errors': false_auto_rejection+wrong_update}
