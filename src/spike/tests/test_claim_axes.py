from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from foundation.claim_axes import checked_claim_axes, assess_expected_axes
from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter
from foundation.runtime import ContractError
from run_semantic_stability import load_design, run_suite
from test_arithmetic import extraction
from test_source_handles import wire_review, PAYLOAD, CONFIG
from test_structured_output import response


FIXTURE, PROTOCOL = load_design("observation-claim-axes-v1.json")


def raw_review():
    raw = wire_review()
    for c in raw["claims"]:
        c.update(attribution={"speaker": "system", "stance": "endorsed"}, boundary_status="PASS")
    raw["criteria"].append({"id": "attribution", "status": "PASS", "quotes": [], "rationale": "Mock classified attribution."})
    return raw


def adapter(raw=None):
    return DeepSeekAdapter(CONFIG, Mock(side_effect=[
        response(extraction(PAYLOAD, value="120"), "submit_extraction"),
        response(raw_review() if raw is None else raw)]))


class ClaimAxisTests(unittest.TestCase):
    def test_typed_judgments_are_stripped_only_for_existing_source_checker(self):
        raw = raw_review()
        checked = checked_claim_axes(raw)
        self.assertIn("attribution", raw["claims"][0])
        self.assertNotIn("attribution", checked["claims"][0])
        self.assertNotIn("boundary_status", checked["claims"][0])
        self.assertEqual(checked["criteria"], raw["criteria"])

    def test_contradictory_or_missing_axes_cannot_hide_in_overall_pass(self):
        for change in (lambda c: c.update(boundary_status="FAIL"),
                       lambda c: c.update(attribution={"speaker": "unresolved", "stance": "reported"}),
                       lambda c: c.pop("attribution"),
                       lambda c: c.update(attribution={"speaker": "invented", "stance": "reported"})):
            raw = raw_review()
            change(raw["claims"][0])
            with self.assertRaises(ContractError):
                checked_claim_axes(raw)

    def test_candidate_attribution_does_not_mechanically_assert_source_truth(self):
        raw = raw_review()
        raw["claims"][0].update(attribution={"speaker": "learner", "stance": "reported"},
                                  status="FAIL", support="unsupported", sources=[], inspected_sources=["source_0", "source_1"])
        next(c for c in raw["criteria"] if c["id"] == "grounding")["status"] = "FAIL"
        checked = checked_claim_axes(raw)
        self.assertEqual(next(c for c in checked["criteria"] if c["id"] == "boundary")["status"], "PASS")

    def test_merged_report_and_endorsement_cannot_satisfy_both_labelled_spans(self):
        candidate = {"description": "A report. An endorsement."}
        raw = {"claims": [{"field": "description", "text": candidate["description"],
                          "attribution": {"speaker": "learner", "stance": "reported"}, "boundary_status": "PASS"}]}
        labels = [
            {"field": "description", "text": "A report.", "attribution": {"speaker": "learner", "stance": "reported"}, "boundary_status": "PASS"},
            {"field": "description", "text": "An endorsement.", "attribution": {"speaker": "system", "stance": "endorsed"}, "boundary_status": "FAIL"}]
        self.assertEqual([x["matches"] for x in assess_expected_axes(raw, candidate, labels)], [True, False])
        self.assertEqual(assess_expected_axes({}, candidate, []), [])

    def test_frozen_report_quartet_changes_source_without_changing_candidate_axes(self):
        quartet = FIXTURE["cases"][:4]
        self.assertEqual(len({c["candidate"]["description"] for c in quartet}), 1)
        self.assertEqual(len({json.dumps(c["expected_claim_axes"]) for c in quartet}), 1)
        self.assertEqual([c["expected_criteria"]["grounding"] for c in quartet], ["PASS", "FAIL", "FAIL", "FAIL"])
        self.assertTrue(all(c["expected_criteria"]["boundary"] == "PASS" for c in quartet))


class ClaimAxisRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.h, _, self.runtime, self.token, self.ctx, _, _ = setup_boundary(
            prepare_candidate=False, protocol_payload=PROTOCOL, destination=CONFIG.base_url)
        self.candidate = self.runtime.propose(self.ctx, "O", "r1", PAYLOAD)

    def test_attribution_uncertainty_prevents_commit(self):
        raw = raw_review()
        raw["claims"][0]["attribution"]["speaker"] = "unresolved"
        next(c for c in raw["criteria"] if c["id"] == "attribution")["status"] = "UNRESOLVED"
        review = self.runtime.validate_with_llm(self.token, self.candidate, adapter(raw))
        self.assertEqual(review.status, "UNRESOLVED")
        self.assertEqual(self.runtime.commit(self.token, self.candidate, review.identity).status, "ValidationFailed")

    def test_axes_are_preserved_and_revalidated_before_commit(self):
        review = self.runtime.validate_with_llm(self.token, self.candidate, adapter())
        self.assertEqual(self.runtime.validate(self.candidate, review.identity), "")
        details = json.loads(review.details_json)
        self.assertEqual(details["claims"][0]["attribution"]["speaker"], "system")
        details["claims"][0]["boundary_status"] = "FAIL"
        self.runtime._reviews[review.identity] = replace(review, details_json=json.dumps(details))
        self.assertIn("ClaimAxisAggregateMismatch", self.runtime.validate(self.candidate, review.identity))

    def test_correct_final_status_cannot_hide_wrong_annotated_axis_in_runner(self):
        fixture = deepcopy(FIXTURE)
        fixture.update(planned_repetitions=1, planned_model_calls=1, initial_model_calls=2, max_model_calls=2)
        fixture["cases"] = [{"id": "mock_axis_mismatch", "candidate": PAYLOAD, "work": {"task": "task", "text": "8 * 15 = 120"},
            "expected_status": "PASS", "expected_commit": "Committed", "expected_criteria": {"attribution": "PASS"},
            "expected_claim_axes": [{"field": "description", "text": PAYLOAD["description"],
                "attribution": {"speaker": "learner", "stance": "reported"}, "boundary_status": "PASS"}]}]
        llm = adapter()
        with tempfile.TemporaryDirectory() as directory:
            result = run_suite(CONFIG, Path(directory), fixture, PROTOCOL, llm)
        self.assertEqual(result["runs"][0]["commit_status"], "Committed")
        self.assertEqual(result["status"], "NON_SUCCESS")
        self.assertEqual(result["matched_runs"], 0)
        self.assertEqual(result["claim_axis_mismatches"], 1)
        self.assertEqual(result["false_positives"], 0)
        self.assertNotIn("expected_claim_axes", json.dumps(llm.records))


if __name__ == "__main__":
    unittest.main()
