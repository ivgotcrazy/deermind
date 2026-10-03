from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from foundation.arithmetic import check_arithmetic_extraction
from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, LLMConfig, ModelFailure
from foundation.runtime import ContractError
from foundation.security import AccessDenied
from run_semantic_stability import run_suite, load_design
from test_source_review import make_review
from test_absence_review import response


PROTOCOL = json.loads((Path(__file__).parents[1] / "protocols/observation-smoke-v6.json").read_text(encoding="utf-8"))
PAYLOAD = {"description": "Eight times fifteen equals 125."}


def extraction(payload=PAYLOAD, value="125", stance="asserted_true", operator="multiply", left="8", right="15"):
    return {"segments": [{"field": "description", "text": payload["description"], "coverage": "COMPLETE",
                           "assertions": [{"operator": operator, "left": left, "right": right, "value": value, "stance": stance}]}]}


def passing_review(payload=PAYLOAD, mapping="PASS"):
    result = make_review(payload, "8 * 15 = 120")
    for c in result["claims"]:
        c.update(support="supported", inspected_sources=[])
    result["criteria"].append({"id": "arithmetic_mapping", "status": mapping,
                               "quotes": [{"field": "description", "text": payload["description"]}],
                               "rationale": "Injected mapping judgment for boundary testing."})
    return result


class ExactArithmeticTests(unittest.TestCase):
    def test_endorsement_denial_and_report_are_distinct(self):
        for value, stance, expected in (("125", "asserted_true", "FAIL"), ("120", "asserted_true", "PASS"),
                                       ("125", "asserted_false", "PASS"), ("120", "asserted_false", "FAIL"),
                                       ("125", "reported_only", "PASS")):
            with self.subTest(value=value, stance=stance):
                self.assertEqual(check_arithmetic_extraction(extraction(value=value, stance=stance), PAYLOAD)["status"], expected)

    def test_decimal_addition_and_fraction_division_are_exact(self):
        for op, left, right, value in (("add", "0.1", "0.2", "0.3"), ("divide", "1", "8", "0.125"),
                                       ("subtract", "-2", "3", "-5")):
            result = check_arithmetic_extraction(extraction(operator=op, left=left, right=right, value=value), PAYLOAD)
            self.assertEqual(result["status"], "PASS")
        result = check_arithmetic_extraction(extraction(operator="divide", left="1", right="3", value="0.33333333"), PAYLOAD)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["checks"][0]["computed"], "1/3")

    def test_unsupported_or_ambiguous_math_is_unresolved(self):
        value = extraction(operator="divide", right="0")
        self.assertEqual(check_arithmetic_extraction(value, PAYLOAD)["status"], "UNRESOLVED")
        value = extraction(value="120")
        value["segments"][0]["coverage"] = "UNRESOLVED"
        self.assertEqual(check_arithmetic_extraction(value, PAYLOAD)["status"], "UNRESOLVED")

    def test_unsafe_or_unbounded_numbers_and_operators_are_rejected(self):
        for number in (True, 125, "NaN", "1e99", "1/3", "__import__('os')", "9" * 100):
            with self.subTest(number=number), self.assertRaises(ContractError):
                check_arithmetic_extraction(extraction(value=number), PAYLOAD)
        with self.assertRaises(ContractError):
            check_arithmetic_extraction(extraction(operator="eval"), PAYLOAD)

    def test_full_text_coverage_does_not_prove_semantic_mapping(self):
        value = extraction()
        value["segments"][0]["text"] = "Eight times fifteen"
        with self.assertRaisesRegex(ContractError, "Coverage"):
            check_arithmetic_extraction(value, PAYLOAD)
        # A wrong extraction can compute correctly: independent semantic review is mandatory.
        self.assertEqual(check_arithmetic_extraction(extraction(value="120"), PAYLOAD)["status"], "PASS")


class ArithmeticRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.h, self.s, self.r, self.token, self.ctx, _, _ = setup_boundary(
            prepare_candidate=False, protocol_payload=PROTOCOL, destination="https://api.deepseek.com")
        self.candidate = self.r.propose(self.ctx, "O", "r1", PAYLOAD)

    def adapter(self, extract=None, review=None):
        return DeepSeekAdapter(LLMConfig("test-key"), Mock(side_effect=[
            response(extract if extract is not None else extraction()), response(review if review is not None else passing_review())]))

    def test_exact_calculation_overrides_semantic_pass_and_is_recomputed_at_commit(self):
        adapter = self.adapter()
        review = self.r.validate_with_llm(self.token, self.candidate, adapter)
        self.assertEqual(review.status, "FAIL")
        evidence = self.h.get(review.execution).payload
        self.assertEqual(evidence["semantic_status"], "PASS")
        self.assertEqual(evidence["arithmetic_result"]["checks"][0]["computed"], "120")
        self.assertEqual(self.r.commit(self.token, self.candidate, review.identity).status, "ValidationFailed")
        self.assertEqual(adapter.calls, 2)
        self.assertEqual([r["purpose"] for r in adapter.records], ["ArithmeticExtraction", "ObservationSemanticValidation"])
        self.r._reviews[review.identity] = replace(review, status="PASS")
        self.assertEqual(self.r.commit(self.token, self.candidate, review.identity).status, "ValidationFailed")

    def test_bad_mapping_blocks_even_when_extracted_calculation_passes(self):
        for mapping in ("FAIL", "UNRESOLVED"):
            self.setUp()
            review = self.r.validate_with_llm(self.token, self.candidate,
                                             self.adapter(extraction(value="120"), passing_review(mapping=mapping)))
            self.assertEqual(review.status, "UNRESOLVED")
            self.assertEqual(self.r.commit(self.token, self.candidate, review.identity).status, "ValidationFailed")

    def test_correct_assertion_can_commit(self):
        payload = {"description": "Eight times fifteen equals 120."}
        candidate = self.r.propose(self.ctx, "O", "r2", payload)
        review = self.r.validate_with_llm(self.token, candidate,
                                         self.adapter(extraction(payload, value="120"), passing_review(payload)))
        self.assertEqual(self.r.commit(self.token, candidate, review.identity).status, "Committed")

    def test_extraction_cannot_be_reused_for_another_candidate(self):
        review = self.r.validate_with_llm(self.token, self.candidate, self.adapter())
        ref = self.r._arithmetic_executions[self.candidate.identity]
        other = self.r.propose(self.ctx, "O", "r2", {"description": "Different candidate"})
        with self.assertRaisesRegex(ContractError, "BindingMismatch"):
            self.r._checked_arithmetic(other, ref)

    def test_access_revocation_between_stages_prevents_review_call(self):
        def first(*args):
            control = self.r.execution("Revoke", self.ctx.subject, {})
            self.s.revoke("read-data", control)
            return response(extraction())
        adapter = DeepSeekAdapter(LLMConfig("test-key"), Mock(side_effect=first))
        with self.assertRaises(AccessDenied):
            self.r.validate_with_llm(self.token, self.candidate, adapter)
        self.assertEqual(adapter.calls, 1)

    def test_source_conflict_recheck_reuses_extraction_once(self):
        payload = {"description": 'The learner wrote, "8 * 15 = 120".'}
        candidate = self.r.propose(self.ctx, "O", "r2", payload)
        first = passing_review(payload)
        first["claims"][0].update(kind="direct_quote", reported_quote="8 * 15 = 120",
                                   status="FAIL", support="text_absent", sources=[])
        next(c for c in first["criteria"] if c["id"] == "grounding")["status"] = "FAIL"
        second = passing_review(payload)
        second["claims"][0].update(kind="direct_quote", reported_quote="8 * 15 = 120")
        adapter = DeepSeekAdapter(LLMConfig("test-key", max_calls=3), Mock(side_effect=[
            response(extraction(payload, value="120", stance="reported_only")), response(first), response(second)]))
        review = self.r.validate_with_llm(self.token, candidate, adapter)
        self.assertEqual([r.status for r in self.r.validation_history(candidate)], ["UNRESOLVED", "PASS"])
        self.assertEqual(self.r.validate_with_llm(self.token, candidate, adapter), review)
        self.assertEqual([r["purpose"] for r in adapter.records],
                         ["ArithmeticExtraction", "ObservationSemanticValidation", "ObservationSemanticRecheck"])
        self.assertEqual(self.r.commit(self.token, candidate, review.identity).status, "Committed")
        self.assertIsNone(self.h.get(self.candidate.record.ref))

    def test_failed_extraction_does_not_send_second_call_or_retry(self):
        adapter = DeepSeekAdapter(LLMConfig("test-key"), Mock(side_effect=ModelFailure("ProviderTimeout")))
        with self.assertRaises(ModelFailure):
            self.r.validate_with_llm(self.token, self.candidate, adapter)
        with self.assertRaisesRegex(ContractError, "AlreadyAttempted"):
            self.r.validate_with_llm(self.token, self.candidate, adapter)
        self.assertEqual(adapter.calls, 1)

    def test_runner_reports_raw_semantic_pass_and_arithmetic_override_separately(self):
        fixture, _ = load_design("observation-arithmetic-v1.json")
        fixture.update(planned_repetitions=1, planned_model_calls=1, initial_model_calls=2, max_model_calls=2,
                       cases=[{"id": "injected_false_pass", "candidate": PAYLOAD,
                               "work": {"text": "8 * 15 = 120"}, "expected_status": "FAIL",
                               "expected_commit": "ValidationFailed", "expected_criteria": {"arithmetic_mapping": "PASS"},
                               "expected_arithmetic_status": "FAIL"}])
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as directory:
            summary = run_suite(adapter.config, Path(directory), fixture, PROTOCOL, adapter)
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["arithmetic_overrides"], 1)
            self.assertEqual(summary["extraction_calls"], 1)
            self.assertEqual(summary["model_calls"], 2)


if __name__ == "__main__":
    unittest.main()
