from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, LLMConfig
from foundation.runtime import ContractError
from foundation.source_conflicts import check_absence_review
from run_semantic_stability import load_design, schedule
from test_source_review import make_review, REF
from test_absence_review import output as quote_review, response, SOURCE, PAYLOAD


PROTOCOL = json.loads((Path(__file__).parents[1] / "protocols/observation-smoke-v5.json").read_text(encoding="utf-8"))
WORK = {"task": "Solve the calculation.", "text": "One solution was submitted."}
CONTEXT = [{"ref": dict(REF), "content": WORK}]
SCOPE = [{"ref": dict(REF), "field": key} for key in WORK]
CLAIM = {"description": "The learner submitted two solutions."}


def unsupported_review():
    result = make_review(CLAIM, WORK["text"])
    result["claims"][0].update(support="unsupported", status="FAIL", sources=[], inspected_sources=deepcopy(SCOPE))
    next(c for c in result["criteria"] if c["id"] == "grounding")["status"] = "FAIL"
    return result


class SupportContractTests(unittest.TestCase):
    def check(self, value, candidate=CLAIM, context=CONTEXT):
        return check_absence_review(value, candidate, PROTOCOL["criteria"], context, support_audit=True)

    def test_unsupported_assertion_can_fail_without_fabricating_a_quote(self):
        status, _, conflicts = self.check(unsupported_review())
        self.assertEqual((status, conflicts), ("FAIL", []))

    def test_scope_must_cover_all_exact_string_fields_without_duplicates(self):
        for scope in ([], SCOPE[:1], SCOPE + SCOPE[:1], [{"ref": {**REF, "revision": "2"}, "field": "text"}]):
            value = unsupported_review()
            value["claims"][0]["inspected_sources"] = scope
            with self.subTest(scope=scope), self.assertRaises(ContractError):
                self.check(value)

    def test_direct_quote_cannot_use_unsupported_to_bypass_absence_contradiction(self):
        value = quote_review()
        value["claims"][0].update(support="unsupported", inspected_sources=deepcopy(SCOPE))
        with self.assertRaisesRegex(ContractError, "DirectQuoteCannotBypass"):
            self.check(value, PAYLOAD)
        value["claims"][0]["support"] = "text_absent"
        context = [{"ref": dict(REF), "content": {**WORK, "text": SOURCE}}]
        self.assertEqual(self.check(value, PAYLOAD, context)[0], "UNRESOLVED")

    def test_uncertainty_and_boundary_violation_are_separate_axes(self):
        value = unsupported_review()
        value["claims"][0].update(support="uncertain", status="UNRESOLVED", inspected_sources=[])
        next(c for c in value["criteria"] if c["id"] == "grounding")["status"] = "UNRESOLVED"
        self.assertEqual(self.check(value)[0], "UNRESOLVED")
        next(c for c in value["criteria"] if c["id"] == "boundary")["status"] = "FAIL"
        self.assertEqual(self.check(value)[0], "FAIL")

    def test_paraphrase_need_not_match_source_wording(self):
        payload = {"description": "The learner asked for an explanation."}
        text = "Please walk me through this calculation."
        context = [{"ref": dict(REF), "content": {"text": text}}]
        value = make_review(payload, text)
        value["claims"][0].update(support="supported", inspected_sources=[])
        self.assertEqual(self.check(value, payload, context)[0], "PASS")

    def test_scope_existence_is_not_a_semantic_classifier(self):
        value = unsupported_review()
        # A scripted false denial still passes structural checks. The LLM must
        # assess support; declaring field coverage is not proof of actual reasoning.
        context = [{"ref": dict(REF), "content": {**WORK, "text": CLAIM["description"]}}]
        self.assertEqual(self.check(value, CLAIM, context)[0], "FAIL")

    def test_v4_does_not_silently_accept_v5_contract(self):
        with self.assertRaises(ContractError):
            check_absence_review(unsupported_review(), CLAIM, PROTOCOL["criteria"], CONTEXT)

    def test_new_fixture_pairs_change_source_and_preserve_candidate(self):
        fixture, _ = load_design("observation-support-v1.json")
        self.assertEqual(len(schedule(fixture)), 32)
        cases = {c["id"]: c for c in fixture["cases"]}
        for positive, negative in (("additional_solution_supported_positive", "additional_solution_unsupported_negative"),
                                   ("independent_request_paraphrase_positive", "independent_request_contradiction_negative")):
            self.assertEqual(cases[positive]["candidate"], cases[negative]["candidate"])
            self.assertNotEqual(cases[positive]["work"], cases[negative]["work"])


class SupportRuntimeTests(unittest.TestCase):
    def test_unsupported_review_is_valid_but_cannot_commit(self):
        h, _, runtime, token, context, _, _ = setup_boundary(
            prepare_candidate=False, protocol_payload=PROTOCOL, destination="https://api.deepseek.com", work_payload=WORK)
        candidate = runtime.propose(context, "O", "r1", CLAIM)
        adapter = DeepSeekAdapter(LLMConfig("test-key"), Mock(return_value=response(unsupported_review())))
        review = runtime.validate_with_llm(token, candidate, adapter)
        self.assertEqual(review.status, "FAIL")
        self.assertEqual(runtime.commit(token, candidate, review.identity).status, "ValidationFailed")
        self.assertIsNone(h.get(candidate.record.ref))
        self.assertEqual(adapter.calls, 1)

    def test_v5_recheck_preserves_once_only_bound_and_commit_revalidation(self):
        h, _, runtime, token, context, _, _ = setup_boundary(
            prepare_candidate=False, protocol_payload=PROTOCOL, destination="https://api.deepseek.com", work_payload={"text": SOURCE})
        candidate = runtime.propose(context, "O", "r1", PAYLOAD)
        first, second = quote_review(), quote_review("supported")
        for value in (first, second):
            for claim in value["claims"]:
                claim["inspected_sources"] = []
        adapter = DeepSeekAdapter(LLMConfig("test-key"), Mock(side_effect=[response(first), response(second)]))
        review = runtime.validate_with_llm(token, candidate, adapter)
        self.assertEqual([r.status for r in runtime.validation_history(candidate)], ["UNRESOLVED", "PASS"])
        self.assertEqual(runtime.validate_with_llm(token, candidate, adapter), review)
        self.assertEqual(adapter.calls, 2)
        self.assertEqual(runtime.commit(token, candidate, review.identity).status, "Committed")


if __name__ == "__main__":
    unittest.main()
