from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, LLMConfig, ModelFailure
from foundation.runtime import ContractError
from foundation.semantic_review import check_criteria_review
from run_semantic_regression import run_pair


ROOT = Path(__file__).parents[1]
PROTOCOL = json.loads((ROOT / "protocols/observation-smoke-v2.json").read_text(encoding="utf-8"))
FIXTURE = json.loads((ROOT / "fixtures/observation-omission-v1.json").read_text(encoding="utf-8"))


def review_for(case):
    # Scripted decisions test the transport/contract, not semantic accuracy.
    return {"reviewed_fields": ["description"], "criteria": [
        {"id": criterion["id"], "status": case["expected_criteria"].get(criterion["id"], "PASS"),
         "quotes": [] if case["expected_criteria"].get(criterion["id"]) == "FAIL"
         else [{"field": "description", "text": case["candidate"]["description"]}],
         "rationale": "Explicit fixture decision for structural testing."}
        for criterion in PROTOCOL["criteria"]]}


def response(output):
    return {"model": "mock", "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(output)}}]}


class CriterionContractTests(unittest.TestCase):
    def setUp(self):
        self.case = FIXTURE["cases"][1]
        self.payload = self.case["candidate"]
        self.output = review_for(self.case)

    def check(self, output):
        return check_criteria_review(output, self.payload, PROTOCOL["criteria"])

    def test_aggregate_requires_all_pass_and_preserves_fail_or_unresolved(self):
        self.assertEqual(self.check(self.output)[0], "PASS")
        self.output["criteria"][2]["status"] = "UNRESOLVED"
        self.assertEqual(self.check(self.output)[0], "UNRESOLVED")
        self.output["criteria"][0]["status"] = "FAIL"
        self.assertEqual(self.check(self.output)[0], "FAIL")

    def test_missing_duplicate_unknown_or_unreviewed_criteria_cannot_pass(self):
        mutations = []
        output = deepcopy(self.output)
        output["criteria"].pop()
        mutations.append(output)
        output = deepcopy(self.output)
        output["criteria"][0]["id"] = output["criteria"][1]["id"]
        mutations.append(output)
        output = deepcopy(self.output)
        output["criteria"][0]["id"] = "invented"
        mutations.append(output)
        output = deepcopy(self.output)
        output["reviewed_fields"] = []
        mutations.append(output)
        output = deepcopy(self.output)
        output["status"] = "PASS"
        mutations.append(output)
        for output in mutations:
            with self.subTest(output=output), self.assertRaises(ContractError):
                self.check(output)

    def test_context_only_or_edited_quote_cannot_support_original_candidate(self):
        negative = FIXTURE["cases"][0]
        output = review_for(negative)
        output["criteria"][2].update(status="PASS", quotes=[{
            "field": "description", "text": "The final answer 120 is incorrect; the correct answer is 105."}])
        with self.assertRaisesRegex(ContractError, "QuoteNotInExactCandidate"):
            check_criteria_review(output, negative["candidate"], PROTOCOL["criteria"])

    def test_positive_support_pass_needs_quote_but_omission_fail_can_have_none(self):
        self.output["criteria"][2]["quotes"] = []
        with self.assertRaisesRegex(ContractError, "PassingCriterionNeedsCandidateQuote"):
            self.check(self.output)
        self.output["criteria"][2]["status"] = "FAIL"
        self.assertEqual(self.check(self.output)[0], "FAIL")

    def test_whole_candidate_checks_can_pass_without_quotes_but_violation_needs_location(self):
        self.output["criteria"][4]["quotes"] = []
        self.assertEqual(self.check(self.output)[0], "PASS")
        self.output["criteria"][4]["status"] = "FAIL"
        with self.assertRaisesRegex(ContractError, "ViolationNeedsCandidateQuote"):
            self.check(self.output)

    def test_quote_existence_deliberately_does_not_decide_semantic_support(self):
        negative = FIXTURE["cases"][0]
        output = review_for(FIXTURE["cases"][1])
        for row in output["criteria"]:
            row["quotes"] = [{"field": "description", "text": "Answer = 120"}]
        # All quoted bytes exist, but the model's PASS decisions are unsupported.
        # This test prevents a keyword heuristic being smuggled into the checker.
        self.assertEqual(check_criteria_review(output, negative["candidate"], PROTOCOL["criteria"])[0], "PASS")


class CriterionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.h, self.s, self.r, self.token, self.ctx, _, _ = setup_boundary(
            prepare_candidate=False, protocol_payload=PROTOCOL, destination="https://api.deepseek.com")

    def test_rule_and_protocol_use_new_exact_versions(self):
        self.assertEqual(self.ctx.protocol.revision, "v2")
        self.assertTrue(all(ref.revision == "v2" for ref in self.ctx.versions.semantic_bindings))
        old = json.loads((ROOT / "protocols/observation-smoke-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(old["generation_system"], PROTOCOL["generation_system"])

    def test_malformed_evidence_is_logged_and_cannot_be_committed(self):
        case = FIXTURE["cases"][0]
        candidate = self.r.propose(self.ctx, "O", "r1", case["candidate"])
        output = review_for(case)
        output["criteria"][2].update(status="PASS", quotes=[{"field": "description", "text": "invented text"}])
        adapter = DeepSeekAdapter(LLMConfig("test-key"), Mock(return_value=response(output)))
        with self.assertRaisesRegex(ContractError, "QuoteNotInExactCandidate"):
            self.r.validate_with_llm(self.token, candidate, adapter)
        self.assertIsNone(self.h.get(candidate.record.ref))
        self.assertTrue(any(r.kind == "SemanticValidationRejected" for r in self.h.executions.records()))

    def test_exact_criteria_details_are_required_again_at_commit(self):
        case = FIXTURE["cases"][1]
        candidate = self.r.propose(self.ctx, "O", "r1", case["candidate"])
        review = self.r.record_semantic_validation(self.token, candidate, "PASS", "fixture", "FIXTURE", fixture=True)
        self.assertEqual(self.r.commit(self.token, candidate, review.identity).status, "ValidationFailed")
        adapter = DeepSeekAdapter(LLMConfig("test-key"), Mock(return_value=response(review_for(case))))
        review = self.r.validate_with_llm(self.token, candidate, adapter)
        self.assertEqual(json.loads(review.details_json), review_for(case))
        self.assertEqual(self.r.commit(self.token, candidate, review.identity).status, "Committed")


class RegressionRunnerTests(unittest.TestCase):
    def test_negative_and_positive_are_both_required_and_keep_each_output(self):
        transport = Mock(side_effect=[response(review_for(case)) for case in FIXTURE["cases"]])
        config = LLMConfig("test-key")
        adapter = DeepSeekAdapter(config, transport)
        with tempfile.TemporaryDirectory() as directory:
            result = run_pair(config, Path(directory), adapter)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["model_calls"], 2)
            self.assertEqual([c["semantic_status"] for c in result["cases"]], ["FAIL", "PASS"])
            rows = [json.loads(line) for line in (Path(directory) / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(sum(r["kind"] == "model_execution" for r in rows), 2)

    def test_model_failure_is_inconclusive_not_successful_negative_detection(self):
        config = LLMConfig("test-key")
        adapter = DeepSeekAdapter(config, Mock(side_effect=ModelFailure("ProviderHTTPError:503")))
        with tempfile.TemporaryDirectory() as directory:
            result = run_pair(config, Path(directory), adapter)
            self.assertEqual(result["status"], "NON_SUCCESS")
            self.assertEqual([c["regression_result"] for c in result["cases"]], ["INCONCLUSIVE", "INCONCLUSIVE"])
            self.assertEqual(result["model_calls"], 2)


if __name__ == "__main__":
    unittest.main()
