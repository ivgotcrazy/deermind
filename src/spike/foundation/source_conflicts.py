"""Versioned source support checks; semantic support remains an LLM judgment."""

import json

from .runtime import ContractError
from .semantic_review import check_source_review


def check_absence_review(output, candidate, criteria, context, *, support_audit=False):
    if not isinstance(output, dict) or set(output) != {"reviewed_fields", "criteria", "claims"}:
        raise ContractError("InvalidSourceReviewShape")
    claims = output["claims"]
    if not isinstance(claims, list) or any(not isinstance(c, dict) or "support" not in c for c in claims):
        raise ContractError("MissingSupportClassification")
    excluded = {"support", "inspected_sources"} if support_audit else {"support"}
    stripped = {**output, "claims": [{k: v for k, v in c.items() if k not in excluded} for c in claims]}
    status, rationale = check_source_review(stripped, candidate, criteria, context)
    conflicts = []
    for index, claim in enumerate(claims):
        support = claim["support"]
        required = {"supported": "PASS", "text_absent": "FAIL", "speaker_mismatch": "FAIL",
                    "meaning_mismatch": "FAIL", "uncertain": "UNRESOLVED"}
        if support_audit:
            required["unsupported"] = "FAIL"
        if not isinstance(support, str) or support not in required or claim["status"] != required[support]:
            raise ContractError("SupportClassificationStatusMismatch")
        if support in ("speaker_mismatch", "meaning_mismatch") and not claim["sources"]:
            raise ContractError("SemanticDenialNeedsSource")
        if support_audit:
            inspected = claim.get("inspected_sources")
            if not isinstance(inspected, list):
                raise ContractError("MissingSourceInspectionScope")
            expected = {json.dumps({"ref": item["ref"], "field": field}, sort_keys=True)
                        for item in context for field, text in item["content"].items() if isinstance(text, str)}
            seen = set()
            for entry in inspected:
                if not isinstance(entry, dict) or set(entry) != {"ref", "field"}:
                    raise ContractError("InvalidSourceInspectionScope")
                encoded = json.dumps(entry, sort_keys=True)
                if encoded not in expected or encoded in seen:
                    raise ContractError("SourceInspectionOutsideContextOrDuplicate")
                seen.add(encoded)
            if support == "unsupported":
                if claim["kind"] == "direct_quote":
                    raise ContractError("DirectQuoteCannotBypassExistenceCheck")
                if not expected or seen != expected:
                    raise ContractError("UnsupportedNeedsCompleteInspectionScope")
        if support != "text_absent":
            continue
        if claim["kind"] != "direct_quote":
            raise ContractError("VerbatimAbsenceOnlyForDirectQuote")
        quote = claim["reported_quote"]
        matches = [{"ref": item["ref"], "field": field, "text": text}
                   for item in context for field, text in item["content"].items()
                   if isinstance(text, str) and quote in text]
        if matches:
            conflicts.append({"claim_index": index, "reported_quote": quote,
                              "reason": "TextPresentDespiteAbsenceClaim", "matches": matches})
    # A contradictory review has no reliable global verdict, even if it also says FAIL.
    if conflicts:
        return "UNRESOLVED", "SourceExistenceContradiction; " + rationale, conflicts
    return status, rationale, conflicts
