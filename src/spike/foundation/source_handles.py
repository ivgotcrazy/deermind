"""Versioned source-field handles: exact representation, never semantic inference."""

from copy import deepcopy
import json

from .runtime import ContractError


def source_registry(context):
    entries, seen = [], set()
    for item in context:
        for field, text in sorted(item["content"].items()):
            if not isinstance(text, str):
                continue
            key = json.dumps({"ref": item["ref"], "field": field}, sort_keys=True)
            if key in seen:
                raise ContractError("DuplicateSourceField")
            seen.add(key)
            entries.append({"handle": f"source_{len(entries)}", "ref": deepcopy(item["ref"]),
                            "field": field, "text": text})
    if not entries:
        raise ContractError("NoSourceFields")
    return entries


def handle_contract(template, registry):
    contract = deepcopy(template)
    claim = contract["parameters"]["properties"]["claims"]["items"]["properties"]
    choices = {"type": "string", "enum": [r["handle"] for r in registry]}
    for field in ("sources", "inspected_sources"):
        claim[field] = {"type": "array", "items": deepcopy(choices)}
    return contract


def expand_review(wire, registry):
    """Expand only declared handles, never search, guess, rebind or interpret text."""
    if not isinstance(wire, dict) or not isinstance(wire.get("claims"), list):
        raise ContractError("InvalidHandleReview")
    output = deepcopy(wire)
    lookup = {r["handle"]: r for r in registry}
    for claim in output["claims"]:
        if not isinstance(claim, dict):
            raise ContractError("InvalidHandleReview")
        for field in ("sources", "inspected_sources"):
            handles = claim.get(field)
            if (not isinstance(handles, list) or any(not isinstance(h, str) or h not in lookup for h in handles)
                    or len(handles) != len(set(handles))):
                raise ContractError("UnknownOrDuplicateSourceHandle")
            keys = ("ref", "field", "text") if field == "sources" else ("ref", "field")
            claim[field] = [{key: deepcopy(lookup[h][key]) for key in keys} for h in handles]
    return output
