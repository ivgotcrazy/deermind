"""Structural evidence checks only. Semantic support remains the LLM's judgment."""

from .runtime import ContractError


def check_criteria_review(output, candidate_payload, criteria):
    """Validate exact quotes and aggregate predeclared criterion outcomes.

    A substring match proves only quote existence, never semantic entailment.
    Missing meaning is a model FAIL; malformed/misattributed evidence is a protocol error.
    """
    if not isinstance(output, dict) or set(output) != {"reviewed_fields", "criteria"}:
        raise ContractError("InvalidCriteriaReviewShape")
    fields = output["reviewed_fields"]
    if (not isinstance(fields, list) or any(not isinstance(f, str) for f in fields)
            or len(fields) != len(set(fields)) or set(fields) != set(candidate_payload)):
        raise ContractError("IncompleteCandidateFieldCoverage")
    expected = {criterion["id"]: criterion for criterion in criteria}
    if not expected or len(expected) != len(criteria):
        raise ContractError("InvalidCriterionDefinition")
    rows = output["criteria"]
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ContractError("IncompleteCriterionCoverage")
    found, outcomes, reasons = set(), [], []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "status", "quotes", "rationale"}:
            raise ContractError("InvalidCriterionResultShape")
        identity, status = row["id"], row["status"]
        if not isinstance(identity, str) or identity not in expected or identity in found:
            raise ContractError("UnknownOrDuplicateCriterion")
        if status not in ("PASS", "FAIL", "UNRESOLVED"):
            raise ContractError("InvalidCriterionStatus")
        if not isinstance(row["rationale"], str) or not row["rationale"].strip():
            raise ContractError("MissingCriterionRationale")
        if not isinstance(row["quotes"], list):
            raise ContractError("InvalidCandidateQuotes")
        for quote in row["quotes"]:
            if not isinstance(quote, dict) or set(quote) != {"field", "text"}:
                raise ContractError("InvalidCandidateQuoteShape")
            field, text = quote["field"], quote["text"]
            if (not isinstance(field, str) or field not in candidate_payload
                    or not isinstance(candidate_payload[field], str)
                    or not isinstance(text, str) or not text.strip()
                    or text not in candidate_payload[field]):
                raise ContractError("QuoteNotInExactCandidate")
        mode = expected[identity]["evidence_mode"]
        if mode not in ("positive_support", "whole_candidate"):
            raise ContractError("InvalidCriterionEvidenceMode")
        if status == "PASS" and mode == "positive_support" and not row["quotes"]:
            raise ContractError("PassingCriterionNeedsCandidateQuote")
        if status == "FAIL" and mode == "whole_candidate" and not row["quotes"]:
            raise ContractError("ViolationNeedsCandidateQuote")
        found.add(identity)
        outcomes.append(status)
        reasons.append(f"{identity}={status}: {row['rationale']}")
    overall = "FAIL" if "FAIL" in outcomes else "UNRESOLVED" if "UNRESOLVED" in outcomes else "PASS"
    return overall, " | ".join(reasons)
