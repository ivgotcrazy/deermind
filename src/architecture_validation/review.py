"""Derive the overall result from all required semantic check verdicts.

The caller validates the scope/schema first. This never reinterprets a check's
meaning, edits its verdict, or overrides FAIL/UNRESOLVED with model confidence.
"""


def aggregate_review(review):
    checks=review.get('checks',[])
    if not checks:return 'UNRESOLVED'
    verdicts=[c.get('verdict') for c in checks]
    if 'FAIL' in verdicts:return 'FAIL'
    if all(v=='PASS' for v in verdicts) and all(c.get('reason') for c in checks):return 'PASS'
    return 'UNRESOLVED'
