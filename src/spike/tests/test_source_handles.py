from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, LLMConfig
from foundation.runtime import ContractError
from foundation.source_handles import source_registry, handle_contract, expand_review
from foundation.structured_output import matches_schema
from run_semantic_stability import load_design
from test_arithmetic import extraction, passing_review
from test_structured_output import response


FIXTURE, PROTOCOL = load_design("observation-source-handles-v1.json")
PAYLOAD = {"description": "Eight times fifteen equals 120."}
CONFIG = LLMConfig("test-key", base_url="https://api.deepseek.com/beta", max_calls=3)
CONTEXT = [{"ref": {"space": "fact", "identity": "work", "revision": "1"},
            "content": {"task": "A task.", "text": "8 * 15 = 120", "metadata": 7}}]


def wire_review(payload=PAYLOAD):
    review = passing_review(payload)
    for claim in review["claims"]:
        claim["sources"] = ["source_1"]
        claim["inspected_sources"] = []
    return review


class SourceHandleTests(unittest.TestCase):
    def test_registry_preserves_exact_revision_field_and_whole_text(self):
        registry = source_registry(CONTEXT)
        self.assertEqual([r["field"] for r in registry], ["task", "text"])
        expanded = expand_review(wire_review(), registry)
        self.assertEqual(expanded["claims"][0]["sources"], [{
            "ref": CONTEXT[0]["ref"], "field": "text", "text": "8 * 15 = 120"}])
        self.assertEqual(wire_review()["claims"][0]["sources"], ["source_1"])
        changed = deepcopy(CONTEXT)
        changed[0]["ref"]["revision"] = "2"
        self.assertNotEqual(source_registry(changed), registry)

    def test_unknown_duplicate_or_legacy_objects_are_rejected_without_guessing(self):
        for field in ("sources", "inspected_sources"):
            for value in (["source_99"], ["source_1", "source_1"], [{"field": "content.text"}], [1], None):
                with self.subTest(field=field, value=value):
                    raw = wire_review()
                    raw["claims"][0][field] = value
                    with self.assertRaises(ContractError):
                        expand_review(raw, source_registry(CONTEXT))

    def test_schema_enum_is_only_this_context_and_duplicate_sources_are_rejected(self):
        registry = source_registry(CONTEXT)
        contract = handle_contract(PROTOCOL["output_contracts"]["validation"], registry)
        raw = wire_review()
        self.assertTrue(matches_schema(raw, contract["parameters"]))
        raw["claims"][0]["sources"] = ["source_2"]
        self.assertFalse(matches_schema(raw, contract["parameters"]))
        with self.assertRaisesRegex(ContractError, "DuplicateSourceField"):
            source_registry(CONTEXT + CONTEXT)

    def test_targeted_cases_retain_prior_labels_without_posthoc_weakening(self):
        old, _ = load_design("observation-support-structured-v1.json")
        old = {c["id"]: c for c in old["cases"]}
        self.assertEqual(len(FIXTURE["cases"]), 7)
        for case in FIXTURE["cases"]:
            self.assertEqual(case, old[case["id"]])
        self.assertEqual(FIXTURE["planned_model_calls"], 14)
        self.assertEqual(FIXTURE["initial_model_calls"], 28)


class SourceHandleRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.h, self.security, self.runtime, self.token, self.ctx, _, _ = setup_boundary(
            prepare_candidate=False, protocol_payload=PROTOCOL, destination=CONFIG.base_url)
        self.candidate = self.runtime.propose(self.ctx, "O", "r1", PAYLOAD)

    def adapter(self, review=None, payload=PAYLOAD):
        return DeepSeekAdapter(CONFIG, Mock(side_effect=[
            response(extraction(payload, value="120"), "submit_extraction"),
            response(wire_review(payload) if review is None else review)]))

    def test_wire_and_expanded_output_are_both_bound_and_commit_rechecks_registry(self):
        adapter = self.adapter()
        review = self.runtime.validate_with_llm(self.token, self.candidate, adapter)
        saved = self.h.get(review.execution).payload
        self.assertEqual(saved["wire_output"]["claims"][0]["sources"], ["source_1"])
        self.assertEqual(saved["details"]["claims"][0]["sources"][0]["field"], "text")
        sent = json.loads(adapter.records[1]["messages"][1]["content"])
        self.assertEqual(saved["source_registry"], sent["source_registry"])
        self.assertEqual(self.runtime.commit(self.token, self.candidate, review.identity).status, "Committed")

    def test_registry_or_raw_handle_tampering_cannot_reuse_review(self):
        for field in ("source_registry", "wire_output"):
            self.setUp()
            review = self.runtime.validate_with_llm(self.token, self.candidate, self.adapter())
            saved = self.h.get(review.execution).payload
            if field == "source_registry":
                saved[field][1]["ref"]["revision"] = "different"
            else:
                saved[field]["claims"][0]["sources"] = ["source_0"]
            altered = self.runtime.execution("SemanticValidationExecution", self.ctx.subject, saved)
            self.runtime._reviews[review.identity] = replace(review, execution=altered)
            self.assertEqual(self.runtime.validate(self.candidate, review.identity), "SourceHandleBindingMismatch")

    def test_valid_handle_does_not_bypass_direct_quote_existence(self):
        payload = {"description": 'The learner wrote, "8 * 15 = 120".'}
        candidate = self.runtime.propose(self.ctx, "O", "r2", payload)
        raw = wire_review(payload)
        raw["claims"][0].update(kind="direct_quote", reported_quote="8 * 15 = 120", sources=["source_0"])
        with self.assertRaisesRegex(ContractError, "DirectQuoteNotInCitedSource"):
            self.runtime.validate_with_llm(self.token, candidate, self.adapter(raw, payload))

    def test_unsupported_requires_all_inspected_handles_and_keeps_failure(self):
        for scope, valid in ((["source_1"], False), (["source_0", "source_1"], True)):
            self.setUp()
            raw = wire_review()
            raw["claims"][0].update(status="FAIL", support="unsupported", sources=[], inspected_sources=scope)
            next(c for c in raw["criteria"] if c["id"] == "grounding")["status"] = "FAIL"
            if not valid:
                with self.assertRaisesRegex(ContractError, "CompleteInspectionScope"):
                    self.runtime.validate_with_llm(self.token, self.candidate, self.adapter(raw))
            else:
                review = self.runtime.validate_with_llm(self.token, self.candidate, self.adapter(raw))
                self.assertEqual(review.status, "FAIL")
                self.assertEqual(self.runtime.commit(self.token, self.candidate, review.identity).status, "ValidationFailed")

    def test_absence_recheck_uses_same_registry_and_preserves_both_wire_outputs(self):
        payload = {"description": 'The learner wrote, "8 * 15 = 120".'}
        candidate = self.runtime.propose(self.ctx, "O", "r2", payload)
        first = wire_review(payload)
        first["claims"][0].update(kind="direct_quote", reported_quote="8 * 15 = 120", sources=[], support="text_absent", status="FAIL")
        next(c for c in first["criteria"] if c["id"] == "grounding")["status"] = "FAIL"
        second = wire_review(payload)
        second["claims"][0].update(kind="direct_quote", reported_quote="8 * 15 = 120")
        adapter = DeepSeekAdapter(CONFIG, Mock(side_effect=[
            response(extraction(payload, value="120", stance="reported_only"), "submit_extraction"),
            response(first), response(second)]))
        review = self.runtime.validate_with_llm(self.token, candidate, adapter)
        history = self.runtime.validation_history(candidate)
        self.assertEqual([r.status for r in history], ["UNRESOLVED", "PASS"])
        a, b = [self.h.get(r.execution).payload for r in history]
        self.assertEqual(a["source_registry"], b["source_registry"])
        self.assertNotEqual(a["wire_output"], b["wire_output"])
        self.assertEqual(self.runtime.validate_with_llm(self.token, candidate, adapter), review)
        self.assertEqual(adapter.calls, 3)
        self.assertEqual(self.runtime.commit(self.token, candidate, review.identity).status, "Committed")


if __name__ == "__main__":
    unittest.main()
