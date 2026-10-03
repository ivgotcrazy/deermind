"""Check typed LLM judgments and aggregation, never classify natural language."""

from copy import deepcopy

from .runtime import ContractError


def checked_claim_axes(output):
    if not isinstance(output, dict) or not isinstance(output.get("claims"), list) or not output["claims"]:
        raise ContractError("MissingClaimAxes")
    stripped = deepcopy(output)
    boundaries, unresolved = [], False
    for claim in stripped["claims"]:
        if not isinstance(claim, dict):
            raise ContractError("InvalidClaimAxes")
        attribution = claim.pop("attribution", None)
        boundary = claim.pop("boundary_status", None)
        if (not isinstance(attribution, dict) or set(attribution) != {"speaker", "stance"}
                or attribution["speaker"] not in ("system", "learner", "other", "unresolved")
                or attribution["stance"] not in ("reported", "endorsed", "unresolved")
                or boundary not in ("PASS", "FAIL", "UNRESOLVED")):
            raise ContractError("InvalidClaimAxes")
        unresolved |= "unresolved" in attribution.values()
        boundaries.append(boundary)
    expected = {"attribution": "UNRESOLVED" if unresolved else "PASS",
                "boundary": "FAIL" if "FAIL" in boundaries else "UNRESOLVED" if "UNRESOLVED" in boundaries else "PASS"}
    criteria = output.get("criteria")
    if not isinstance(criteria, list):
        raise ContractError("MissingClaimAxisCriteria")
    for key, status in expected.items():
        rows = [r for r in criteria if isinstance(r, dict) and r.get("id") == key]
        if len(rows) != 1 or rows[0].get("status") != status:
            raise ContractError("ClaimAxisAggregateMismatch:" + key)
    return stripped


def assess_expected_axes(output, candidate, expectations):
    """Offline measurement of prelabelled spans; expectations never enter model inputs."""
    if not expectations:
        return []
    spans, cursors = [], {field: 0 for field in candidate}
    for claim in output["claims"]:
        field, text = claim["field"], claim["text"]
        start = candidate[field].find(text, cursors[field])
        if start < 0:
            raise ValueError("InvalidMeasuredClaimSpan")
        end = start + len(text)
        cursors[field] = end
        spans.append((field, start, end, claim))
    results = []
    for expected in expectations:
        field, text = expected["field"], expected["text"]
        if not text or candidate[field].count(text) != 1:
            raise ValueError("AmbiguousExpectedAxisSpan")
        start = candidate[field].index(text)
        end = start + len(text)
        claims = [c for f, a, b, c in spans if f == field and a < end and b > start]
        matches = bool(claims) and all(c.get("attribution") == expected["attribution"]
            and c.get("boundary_status") == expected["boundary_status"] for c in claims)
        results.append({"expected": expected, "matches": matches,
                        "actual": [{k: c.get(k) for k in ("field", "text", "attribution", "boundary_status")} for c in claims]})
    return results
