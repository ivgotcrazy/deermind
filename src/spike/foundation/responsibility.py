"""Check LLM responsibility classifications and apply the declared admission table."""

from .runtime import ContractError


ADMISSION = {"local_observation": "PASS", "attributed_report": "PASS",
             "ability_inference": "FAIL", "evidence_inference": "FAIL",
             "action_recommendation": "FAIL", "uncertain": "UNRESOLVED"}


def combine_status(*states):
    return "FAIL" if "FAIL" in states else "UNRESOLVED" if "UNRESOLVED" in states else "PASS"


def check_responsibility(output, candidate, *, admission=ADMISSION):
    if admission != ADMISSION:
        raise ContractError("UnsupportedResponsibilityAdmissionTable")
    if not isinstance(output, dict) or set(output) != {"segments"}:
        raise ContractError("InvalidResponsibilityShape")
    segments = output["segments"]
    if not isinstance(segments, list) or not 1 <= len(segments) <= 32:
        raise ContractError("InvalidResponsibilitySegments")
    cursors, checked = {f: 0 for f in candidate}, []
    for segment in segments:
        if not isinstance(segment, dict) or set(segment) != {"field", "text", "role", "rationale"}:
            raise ContractError("InvalidResponsibilitySegment")
        field, text, role = (segment[k] for k in ("field", "text", "role"))
        if (not isinstance(field, str) or field not in candidate or not isinstance(candidate[field], str)
                or not isinstance(text, str) or not text.strip() or not isinstance(role, str) or role not in ADMISSION
                or not isinstance(segment["rationale"], str) or not segment["rationale"].strip()):
            raise ContractError("InvalidResponsibilitySegment")
        start = candidate[field].find(text, cursors[field])
        if start < 0 or candidate[field][cursors[field]:start].strip():
            raise ContractError("IncompleteResponsibilityCoverage")
        cursors[field] = start + len(text)
        checked.append({**segment, "status": admission[role]})
    if any(not isinstance(text, str) or text[cursors[f]:].strip() for f, text in candidate.items()):
        raise ContractError("IncompleteResponsibilityCoverage")
    return {"status": combine_status(*(s["status"] for s in checked)), "segments": checked}


def assess_expected_roles(result, candidate, expectations):
    if not expectations:
        return []
    spans, cursors = [], {f: 0 for f in candidate}
    for segment in result["segments"]:
        field, text = segment["field"], segment["text"]
        start = candidate[field].find(text, cursors[field])
        if start < 0:
            raise ValueError("InvalidResponsibilityMeasurement")
        end = start + len(text)
        spans.append((field, start, end, segment["role"]))
        cursors[field] = end
    measured = []
    for expected in expectations:
        field, text = expected["field"], expected["text"]
        if not text or candidate[field].count(text) != 1:
            raise ValueError("AmbiguousExpectedResponsibilitySpan")
        start = candidate[field].index(text)
        actual = [role for f, a, b, role in spans if f == field and a < start + len(text) and b > start]
        measured.append({"expected": expected, "actual": actual,
                         "matches": bool(actual) and all(role == expected["role"] for role in actual)})
    return measured
