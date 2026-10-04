from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import Mock

from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, ModelFailure
from foundation.runtime import ContractError
from foundation.source_handles import expand_review, source_registry
from run_observation_closeout import s2_eligible
from run_semantic_stability import load_design, run_suite, summarize
from test_arithmetic import extraction
from test_claim_axes import raw_review
from test_responsibility import classification
from test_source_handles import CONFIG, CONTEXT, PAYLOAD, wire_review
from test_structured_output import response


S1, PROTOCOL = load_design("observation-closeout-s1-v1.json")
S2, _ = load_design("observation-closeout-s2-v1.json")


def marker_review(marker="COMPLETE_CONTEXT", unsupported=False):
    raw = raw_review()
    for claim in raw["claims"]:
        claim.pop("inspected_sources")
        claim["inspection_scope"] = marker
        if unsupported:
            claim.update(status="FAIL", support="unsupported", sources=[])
    if unsupported:
        next(c for c in raw["criteria"] if c["id"] == "grounding")["status"] = "FAIL"
    return raw


class CloseoutTests(unittest.TestCase):
    def test_every_fixture_fits_input_limit_with_synthetic_envelopes_only(self):
        for case in S1["cases"] + S2["cases"]:
            with self.subTest(case=case["id"]):
                payload = case["candidate"]
                h, _, runtime, token, ctx, _, _ = setup_boundary(prepare_candidate=False, protocol_payload=PROTOCOL,
                    destination=CONFIG.base_url, work_payload=case["work"])
                candidate = runtime.propose(ctx, "O", "r1", payload)
                raw = wire_review(payload)
                for c in raw["claims"]:
                    c.pop("inspected_sources")
                    c.update(inspection_scope="COMPLETE_CONTEXT", attribution={"speaker":"system","stance":"endorsed"}, boundary_status="PASS")
                raw["criteria"].append({"id":"attribution","status":"PASS","quotes":[],"rationale":"Synthetic envelope only."})
                extracted = {"segments":[{"field":"description","text":payload["description"],"coverage":"COMPLETE","assertions":[]}]}
                # These deliberately synthetic values only test wire shape and length, not meaning.
                adapter = DeepSeekAdapter(CONFIG, Mock(side_effect=[response(classification(payload=payload), "submit_responsibility"),
                    response(extracted, "submit_extraction"), response(raw)]))
                runtime.validate_with_llm(token, candidate, adapter)
                self.assertEqual(adapter.calls, 3)
                self.assertTrue(all(len(json.dumps(r["messages"], ensure_ascii=False)) <= 16000 for r in adapter.records))

    def test_both_batches_frozen_and_old_expectations_retained(self):
        self.assertEqual(S1["protocol_sha256"], S2["protocol_sha256"])
        self.assertEqual((len(S1["cases"]), len(S2["cases"])), (24, 12))
        self.assertEqual(S1["max_model_calls"] + S2["max_model_calls"], 720)
        for c in S1["cases"]:
            old, _ = load_design(c["origin_fixture"])
            original = next(x for x in old["cases"] if x["id"] == c["origin_case_id"])
            for key, value in original.items():
                if key == "expected_criteria":
                    self.assertTrue(all(c[key][k] == v for k, v in value.items()))
                else:
                    self.assertEqual(c[key], value)

    def test_marker_never_inferred_or_accepted_by_old_profile(self):
        registry = source_registry(CONTEXT)
        raw = marker_review("NOT_DECLARED", True)
        expanded = expand_review(raw, registry, "complete-scope-marker-v1")
        self.assertEqual(expanded["claims"][0]["inspected_sources"], [])
        with self.assertRaises(ContractError):
            expand_review(raw, registry)
        for marker in (None, "all", 1):
            with self.assertRaises(ContractError):
                expand_review(marker_review(marker), registry, "complete-scope-marker-v1")

    def test_unsupported_requires_explicit_complete_marker(self):
        for marker in ("NOT_DECLARED", "COMPLETE_CONTEXT"):
            h, _, runtime, token, ctx, _, _ = setup_boundary(prepare_candidate=False, protocol_payload=PROTOCOL, destination=CONFIG.base_url)
            candidate = runtime.propose(ctx, "O", "r1", PAYLOAD)
            adapter = DeepSeekAdapter(CONFIG, Mock(side_effect=[response(classification(), "submit_responsibility"),
                response(extraction(PAYLOAD, value="120"), "submit_extraction"), response(marker_review(marker, True))]))
            if marker == "NOT_DECLARED":
                with self.assertRaisesRegex(ContractError, "CompleteInspectionScope"):
                    runtime.validate_with_llm(token, candidate, adapter)
            else:
                review = runtime.validate_with_llm(token, candidate, adapter)
                self.assertEqual(review.status, "FAIL")
                self.assertEqual(runtime.commit(token, candidate, review.identity).status, "ValidationFailed")

    def test_commit_reexpands_marker_and_rejects_forged_wire_declaration(self):
        h, _, runtime, token, ctx, _, _ = setup_boundary(prepare_candidate=False, protocol_payload=PROTOCOL, destination=CONFIG.base_url)
        candidate = runtime.propose(ctx, "O", "r1", PAYLOAD)
        adapter = DeepSeekAdapter(CONFIG, Mock(side_effect=[response(classification(), "submit_responsibility"),
            response(extraction(PAYLOAD, value="120"), "submit_extraction"), response(marker_review())]))
        review = runtime.validate_with_llm(token, candidate, adapter)
        self.assertEqual(runtime.validate(candidate, review.identity), "")
        saved = h.get(review.execution).payload
        saved["wire_output"]["claims"][0]["inspection_scope"] = "NOT_DECLARED"
        forged = runtime.execution("SemanticValidationExecution", ctx.subject, saved)
        runtime._reviews[review.identity] = replace(review, execution=forged)
        self.assertEqual(runtime.validate(candidate, review.identity), "SourceHandleBindingMismatch")

    def test_extra_extraction_wrapper_still_fails_without_repair(self):
        adapter = DeepSeekAdapter(CONFIG, Mock(return_value=response({"arguments": extraction(PAYLOAD)}, "submit_extraction")))
        with self.assertRaisesRegex(ModelFailure, "OutputSchemaMismatch"):
            adapter.complete([], "ArithmeticExtraction", output_contract=PROTOCOL["output_contracts"]["extraction"])
        self.assertEqual(adapter.calls, 1)

    def test_consecutive_failures_stop_actual_runner_and_prevent_s2(self):
        fixture = deepcopy(S1)
        fixture.update(planned_repetitions=1, planned_model_calls=5, max_model_calls=15)
        fixture["cases"] = [dict(fixture["cases"][0], id=f"case-{i}") for i in range(5)]
        config = replace(CONFIG, max_calls=15)
        adapter = DeepSeekAdapter(config, Mock(side_effect=ModelFailure("ProviderTimeout")))
        with tempfile.TemporaryDirectory() as directory:
            summary = run_suite(config, Path(directory), fixture, PROTOCOL, adapter)
        self.assertEqual(summary["completed_runs"], 3)
        self.assertEqual(summary["not_run"], 2)
        self.assertEqual(summary["stop_reason"], "ConsecutiveProtocolOrRuntimeFailures")
        self.assertFalse(s2_eligible(summary))

    def test_interception_and_component_accuracy_remain_distinct(self):
        fixture = deepcopy(S1)
        fixture.update(planned_repetitions=1, planned_model_calls=1)
        fixture["cases"] = [fixture["cases"][0]]
        row = dict(case_id=fixture["cases"][0]["id"], result="FAIL", expected_status="FAIL", expected_commit="ValidationFailed",
                   semantic_status="FAIL", commit_status="ValidationFailed", criterion_statuses={"boundary":"PASS"})
        summary = summarize([row], fixture, 3)
        self.assertEqual(summary["status"], "NON_SUCCESS")
        self.assertEqual(summary["composite_status"], "PASS")
        row.update(commit_status="Committed", semantic_status="PASS")
        summary = summarize([row], fixture, 3)
        self.assertEqual(summary["stop_reason"], "ForbiddenCommitObserved")
        self.assertFalse(s2_eligible(summary))
