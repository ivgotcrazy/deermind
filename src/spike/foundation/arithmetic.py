"""Exact operations on LLM-extracted assertions; no natural-language classification."""

from fractions import Fraction
import re

from .runtime import ContractError


def number(value):
    # Grammar of a typed decimal value, not a keyword rule over candidate language.
    if not isinstance(value, str) or not re.fullmatch(r"-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?", value):
        raise ContractError("InvalidBoundedDecimal")
    return Fraction(value)


def check_arithmetic_extraction(output, candidate):
    if not isinstance(output, dict) or set(output) != {"segments"}:
        raise ContractError("InvalidArithmeticExtractionShape")
    segments = output["segments"]
    if not isinstance(segments, list) or not 1 <= len(segments) <= 32:
        raise ContractError("InvalidArithmeticSegments")
    cursors, checks, statuses = {f: 0 for f in candidate}, [], []
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict) or set(segment) != {"field", "text", "coverage", "assertions"}:
            raise ContractError("InvalidArithmeticSegmentShape")
        field, text = segment["field"], segment["text"]
        if (not isinstance(field, str) or field not in candidate or not isinstance(candidate[field], str)
                or not isinstance(text, str) or not text.strip()):
            raise ContractError("InvalidArithmeticSpan")
        start = candidate[field].find(text, cursors[field])
        if start < 0 or candidate[field][cursors[field]:start].strip():
            raise ContractError("ArithmeticCoverageGap")
        cursors[field] = start + len(text)
        if segment["coverage"] not in ("COMPLETE", "UNRESOLVED"):
            raise ContractError("InvalidArithmeticCoverageStatus")
        if segment["coverage"] == "UNRESOLVED":
            statuses.append("UNRESOLVED")
        assertions = segment["assertions"]
        if not isinstance(assertions, list) or len(assertions) > 16:
            raise ContractError("InvalidArithmeticAssertions")
        for position, assertion in enumerate(assertions):
            if not isinstance(assertion, dict) or set(assertion) != {"operator", "left", "right", "value", "stance"}:
                raise ContractError("InvalidArithmeticAssertionShape")
            op, stance = assertion["operator"], assertion["stance"]
            if op not in ("add", "subtract", "multiply", "divide") or stance not in ("asserted_true", "asserted_false", "reported_only"):
                raise ContractError("InvalidArithmeticOperatorOrStance")
            left, right, value = (number(assertion[k]) for k in ("left", "right", "value"))
            computed = None if op == "divide" and right == 0 else (
                left + right if op == "add" else left - right if op == "subtract" else
                left * right if op == "multiply" else left / right)
            if stance == "reported_only":
                status = "PASS"  # Quoting another person's wrong equality does not endorse it.
            elif computed is None:
                status = "UNRESOLVED"
            else:
                true = computed == value
                status = "PASS" if true == (stance == "asserted_true") else "FAIL"
            statuses.append(status)
            checks.append({"segment": index, "assertion": position, "computed": str(computed) if computed is not None else None,
                           "claimed": assertion["value"], "stance": stance, "status": status})
    if any(not isinstance(text, str) or text[cursors[field]:].strip() for field, text in candidate.items()):
        raise ContractError("IncompleteArithmeticCoverage")
    overall = "FAIL" if "FAIL" in statuses else "UNRESOLVED" if "UNRESOLVED" in statuses else "PASS"
    return {"status": overall, "checks": checks}


def combine_arithmetic_review(semantic_status, output, arithmetic):
    mappings = [row["status"] for row in output["criteria"] if row["id"] == "arithmetic_mapping"]
    if len(mappings) != 1:
        raise ContractError("RequiredArithmeticMappingReviewMissing")
    mapping = mappings[0]
    if mapping != "PASS":
        return "UNRESOLVED"  # Incorrect extraction cannot establish that the candidate itself is wrong.
    states = (semantic_status, arithmetic["status"])
    return "FAIL" if "FAIL" in states else "UNRESOLVED" if "UNRESOLVED" in states else "PASS"
