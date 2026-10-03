from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, ModelFailure
from foundation.responsibility import check_responsibility
from foundation.runtime import ContractError
from foundation.security import AccessDenied
from run_semantic_stability import load_design, run_suite
from test_arithmetic import extraction
from test_claim_axes import raw_review
from test_source_handles import PAYLOAD, CONFIG, wire_review
from test_structured_output import response


FIXTURE, PROTOCOL = load_design("observation-responsibility-v1.json")


def classification(role="local_observation", payload=PAYLOAD):
    return {"segments": [{"field": "description", "text": payload["description"], "role": role,
                           "rationale": "Injected typed label for local contract tests."}]}


def adapter(role="local_observation"):
    return DeepSeekAdapter(CONFIG, Mock(side_effect=[
        response(classification(role), "submit_responsibility"),
        response(extraction(PAYLOAD, value="120"), "submit_extraction"), response(raw_review())]))


class ResponsibilityTests(unittest.TestCase):
    def test_program_applies_typed_admission_without_reading_meaning(self):
        for role, expected in (("local_observation", "PASS"), ("attributed_report", "PASS"),
                               ("ability_inference", "FAIL"), ("evidence_inference", "FAIL"),
                               ("action_recommendation", "FAIL"), ("uncertain", "UNRESOLVED")):
            self.assertEqual(check_responsibility(classification(role), PAYLOAD)["status"], expected)
        # A wrong LLM label is still a semantic risk; this code does not interpret wording.
        action = {"description": "The system should explain now."}
        self.assertEqual(check_responsibility(classification("local_observation", action), action)["status"], "PASS")

    def test_omitted_tail_unknown_role_and_duplicate_span_fail(self):
        with self.assertRaisesRegex(ContractError, "UnsupportedResponsibilityAdmissionTable"):
            check_responsibility(classification(), PAYLOAD, admission={"action_recommendation": "PASS"})
        for mutation in (lambda x: x["segments"][0].update(text="Eight times fifteen"),
                         lambda x: x["segments"][0].update(role="authorized_action"),
                         lambda x: x["segments"].append(deepcopy(x["segments"][0]))):
            value = classification()
            mutation(value)
            with self.assertRaises(ContractError):
                check_responsibility(value, PAYLOAD)

    def test_old_case_expectations_and_general_review_are_unchanged(self):
        old, protocol = load_design("observation-claim-axes-v1.json")
        old = {c["id"]: c for c in old["cases"]}
        for case in FIXTURE["cases"]:
            if case["id"] in old:
                for key, value in old[case["id"]].items():
                    self.assertEqual(case[key], value)
        for key in ("validation_system", "extraction_system", "criteria"):
            self.assertEqual(PROTOCOL[key], protocol[key])


class ResponsibilityRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.h, self.security, self.runtime, self.token, self.ctx, _, _ = setup_boundary(
            prepare_candidate=False, protocol_payload=PROTOCOL, destination=CONFIG.base_url)
        self.candidate = self.runtime.propose(self.ctx, "O", "r1", PAYLOAD)

    def test_separate_negative_classification_blocks_otherwise_passing_review(self):
        llm = adapter("action_recommendation")
        review = self.runtime.validate_with_llm(self.token, self.candidate, llm)
        saved = self.h.get(review.execution).payload
        self.assertEqual(saved["pre_responsibility_status"], "PASS")
        self.assertEqual(saved["responsibility_result"]["status"], "FAIL")
        self.assertEqual(review.status, "FAIL")
        self.assertEqual(self.runtime.commit(self.token, self.candidate, review.identity).status, "ValidationFailed")
        self.assertNotIn("responsibility_result", json.loads(llm.records[-1]["messages"][1]["content"]))
        self.assertNotIn("classification", json.loads(llm.records[-1]["messages"][1]["content"]))
        self.assertNotIn("untrusted_for_observation", json.dumps(llm.records))

    def test_positive_can_commit_and_uncertain_cannot(self):
        for role, expected in (("local_observation", "Committed"), ("uncertain", "ValidationFailed")):
            self.setUp()
            review = self.runtime.validate_with_llm(self.token, self.candidate, adapter(role))
            self.assertEqual(self.runtime.commit(self.token, self.candidate, review.identity).status, expected)

    def test_missing_or_tampered_classification_cannot_reuse_pass(self):
        review = self.runtime.validate_with_llm(self.token, self.candidate, adapter())
        saved = self.h.get(review.execution).payload
        saved["responsibility_execution"] = None
        ref = self.runtime.execution("SemanticValidationExecution", self.ctx.subject, saved)
        self.runtime._reviews[review.identity] = replace(review, execution=ref)
        self.assertEqual(self.runtime.validate(self.candidate, review.identity), "MissingResponsibilityClassification")
        real = self.runtime._responsibility_executions[self.candidate.identity]
        wrong = self.h.get(real).payload
        wrong["result"]["status"] = "FAIL"
        forged = self.runtime.execution("ResponsibilityClassificationExecution", self.ctx.subject, wrong)
        with self.assertRaisesRegex(ContractError, "ResponsibilityResultMismatch"):
            self.runtime._checked_responsibility(self.candidate, forged)
        other = self.runtime.propose(self.ctx, "O", "r2", {"description": "Other candidate."})
        with self.assertRaisesRegex(ContractError, "ResponsibilityBindingMismatch"):
            self.runtime._checked_responsibility(other, real)

    def test_revocation_after_classification_stops_next_outbound_call(self):
        def classify(*args):
            source = self.runtime.execution("Revoke", self.ctx.subject, {})
            self.security.revoke("read-data", source)
            return response(classification(), "submit_responsibility")
        llm = DeepSeekAdapter(CONFIG, Mock(side_effect=classify))
        with self.assertRaises(AccessDenied):
            self.runtime.validate_with_llm(self.token, self.candidate, llm)
        self.assertEqual(llm.calls, 1)

    def test_classification_failure_does_not_retry_or_continue(self):
        llm = DeepSeekAdapter(CONFIG, Mock(side_effect=ModelFailure("ProviderTimeout")))
        with self.assertRaises(ModelFailure):
            self.runtime.validate_with_llm(self.token, self.candidate, llm)
        with self.assertRaisesRegex(ContractError, "AlreadyAttempted"):
            self.runtime.validate_with_llm(self.token, self.candidate, llm)
        self.assertEqual(llm.calls, 1)

    def test_source_recheck_reuses_bound_classification_and_extraction(self):
        payload = {"description": 'The learner wrote, "8 * 15 = 120".'}
        candidate = self.runtime.propose(self.ctx, "O", "r2", payload)
        second = wire_review(payload)
        second["claims"][0].update(kind="direct_quote", reported_quote="8 * 15 = 120",
                                  attribution={"speaker": "learner", "stance": "reported"}, boundary_status="PASS")
        second["criteria"].append({"id": "attribution", "status": "PASS", "quotes": [], "rationale": "Mock report."})
        first = deepcopy(second)
        first["claims"][0].update(support="text_absent", status="FAIL", sources=[])
        next(c for c in first["criteria"] if c["id"] == "grounding")["status"] = "FAIL"
        llm = DeepSeekAdapter(replace(CONFIG, max_calls=4), Mock(side_effect=[
            response(classification("attributed_report", payload), "submit_responsibility"),
            response(extraction(payload, value="120", stance="reported_only"), "submit_extraction"),
            response(first), response(second)]))
        review = self.runtime.validate_with_llm(self.token, candidate, llm)
        self.assertEqual([r.status for r in self.runtime.validation_history(candidate)], ["UNRESOLVED", "PASS"])
        self.assertEqual(self.runtime.validate_with_llm(self.token, candidate, llm), review)
        self.assertEqual(llm.calls, 4)
        self.assertEqual(self.runtime.commit(self.token, candidate, review.identity).status, "Committed")

    def test_runner_records_interception_and_classification_even_after_later_failure(self):
        f = deepcopy(FIXTURE)
        f.update(planned_repetitions=1, planned_model_calls=1, initial_model_calls=3, max_model_calls=3)
        f["cases"] = [{"id": "mock_interception", "candidate": PAYLOAD, "work": {"task": "task", "text": "8 * 15 = 120"},
                       "expected_status": "FAIL", "expected_commit": "ValidationFailed", "expected_criteria": {},
                       "expected_responsibility_status": "FAIL", "expected_responsibility_roles": [
                           {"field": "description", "text": PAYLOAD["description"], "role": "action_recommendation"}]}]
        for fail in (False, True):
            llm = adapter("action_recommendation")
            if fail:
                llm.transport.side_effect = [response(classification("action_recommendation"), "submit_responsibility"), ModelFailure("ProviderTimeout")]
            with tempfile.TemporaryDirectory() as directory:
                s = run_suite(CONFIG, Path(directory), f, PROTOCOL, llm)
            self.assertEqual(s["responsibility_calls"], 1)
            self.assertEqual(s["runs"][0]["responsibility_status"], "FAIL")
            self.assertEqual(s["responsibility_overrides"], 0 if fail else 1)
            self.assertEqual(s["matched_runs"], 0 if fail else 1)


if __name__ == "__main__":
    unittest.main()
