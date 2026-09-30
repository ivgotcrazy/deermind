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


def check_source_review(output, candidate_payload, criteria, context):
    """Check complete text coverage and exact source links, never semantic entailment.

    The LLM decomposes assertions and judges support/attribution. A complete span
    partition prevents silently omitting text; it cannot prove atomic decomposition.
    Sources must belong to the exact authorized context, not arbitrary stored facts.
    """
    if not isinstance(output, dict) or set(output) != {"reviewed_fields", "criteria", "claims"}:
        raise ContractError("InvalidSourceReviewShape")
    status, reason = check_criteria_review(
        {k: output[k] for k in ("reviewed_fields", "criteria")}, candidate_payload, criteria)
    claims = output["claims"]
    if not isinstance(claims, list) or not claims:
        raise ContractError("MissingClaimCoverage")
    cursors = {field: 0 for field in candidate_payload}
    outcomes = []
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {
                "field", "text", "kind", "reported_quote", "status", "sources", "rationale"}:
            raise ContractError("InvalidClaimShape")
        field, text = claim["field"], claim["text"]
        if (not isinstance(field, str) or field not in cursors
                or not isinstance(candidate_payload[field], str)
                or not isinstance(text, str) or not text.strip()):
            raise ContractError("InvalidClaimSpan")
        payload = candidate_payload[field]
        start = payload.find(text, cursors[field])
        if start < 0 or payload[cursors[field]:start].strip():
            raise ContractError("ClaimCoverageGapOrAlteredText")
        cursors[field] = start + len(text)
        if claim["kind"] not in ("direct_quote", "paraphrase", "local_derivation"):
            raise ContractError("InvalidClaimKind")
        if claim["status"] not in ("PASS", "FAIL", "UNRESOLVED"):
            raise ContractError("InvalidClaimStatus")
        if not isinstance(claim["rationale"], str) or not claim["rationale"].strip():
            raise ContractError("MissingClaimRationale")
        if not isinstance(claim["sources"], list):
            raise ContractError("InvalidClaimSources")
        source_texts = []
        for source in claim["sources"]:
            if not isinstance(source, dict) or set(source) != {"ref", "field", "text"}:
                raise ContractError("InvalidSourceQuoteShape")
            ref = source["ref"]
            if (not isinstance(ref, dict) or set(ref) != {"space", "identity", "revision"}
                    or any(not isinstance(v, str) or not v for v in ref.values())):
                raise ContractError("InvalidSourceRef")
            matches = [item for item in context if item["ref"] == ref]
            if len(matches) != 1:
                raise ContractError("SourceOutsideExactContext")
            source_field, quote = source["field"], source["text"]
            content = matches[0]["content"]
            if (not isinstance(source_field, str) or source_field not in content
                    or not isinstance(content[source_field], str)
                    or not isinstance(quote, str) or not quote.strip()
                    or quote not in content[source_field]):
                raise ContractError("QuoteNotInExactSource")
            source_texts.append(quote)
        reported = claim["reported_quote"]
        if claim["kind"] == "direct_quote":
            if not isinstance(reported, str) or not reported.strip() or reported not in text:
                raise ContractError("DirectQuoteNotInClaim")
            if claim["status"] == "PASS" and not any(reported in quote for quote in source_texts):
                raise ContractError("DirectQuoteNotInCitedSource")
        elif reported is not None:
            raise ContractError("UnexpectedReportedQuote")
        if claim["status"] == "PASS" and not source_texts:
            raise ContractError("PassingClaimNeedsSource")
        outcomes.append(claim["status"])
    if any(not isinstance(value, str) or value[cursors[field]:].strip()
           for field, value in candidate_payload.items()):
        raise ContractError("IncompleteClaimCoverage")
    grounding = "FAIL" if "FAIL" in outcomes else "UNRESOLVED" if "UNRESOLVED" in outcomes else "PASS"
    grounding_rows = [row for row in output["criteria"] if row["id"] == "grounding"]
    if len(grounding_rows) != 1 or grounding_rows[0]["status"] != grounding:
        raise ContractError("GroundingClaimStatusMismatch")
    return status, reason
