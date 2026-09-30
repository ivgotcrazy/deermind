from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, LLMConfig
from foundation.runtime import ContractError
from foundation.semantic_review import check_source_review


ROOT = Path(__file__).parents[1]
PROTOCOL = json.loads((ROOT / "protocols/observation-smoke-v3.json").read_text(encoding="utf-8"))
REF = {"space": "fact", "identity": "work", "revision": "1"}


def make_review(payload, source_text, *, kind="paraphrase", reported_quote=None):
    # Scripted structural contract, not a claim of semantic correctness.
    return {"reviewed_fields": ["description"], "criteria": [
        {"id": c["id"], "status": "PASS", "quotes": [{"field": "description", "text": payload["description"]}],
         "rationale": "Scripted criterion decision."} for c in PROTOCOL["criteria"]],
        "claims": [{"field": "description", "text": payload["description"], "kind": kind,
                    "reported_quote": reported_quote, "status": "PASS",
                    "sources": [{"ref": dict(REF), "field": "text", "text": source_text}],
                    "rationale": "Scripted source support decision."}]}


class SourceContractTests(unittest.TestCase):
    def setUp(self):
        self.payload = {"description": 'The learner wrote, "Please explain division."'}
        self.source = 'Learner: "Please explain division."'
        self.context = [{"ref": dict(REF), "content": {"text": self.source}}]
        self.review = make_review(self.payload, self.source, kind="direct_quote",
                                  reported_quote="Please explain division.")

    def check(self, review=None):
        return check_source_review(review or self.review, self.payload, PROTOCOL["criteria"], self.context)

    def test_valid_direct_quote_and_semantic_paraphrase_are_structurally_allowed(self):
        self.assertEqual(self.check()[0], "PASS")
        self.review["claims"][0].update(kind="paraphrase", reported_quote=None)
        self.assertEqual(self.check()[0], "PASS")

    def test_missing_prefix_middle_tail_or_duplicated_span_cannot_pass(self):
        for spans in (["Please explain division."], ['The learner wrote, '],
                      ['The learner', '"Please explain division."'],
                      [self.payload["description"], self.payload["description"]]):
            output = deepcopy(self.review)
            output["claims"] = [{**deepcopy(self.review["claims"][0]), "text": span,
                                 "kind": "paraphrase", "reported_quote": None} for span in spans]
            with self.subTest(spans=spans), self.assertRaises(ContractError):
                self.check(output)

    def test_ordered_spans_allow_only_whitespace_gaps(self):
        self.payload = {"description": "First.  Second."}
        self.review = make_review(self.payload, self.source)
        self.review["claims"] = [{**deepcopy(self.review["claims"][0]), "text": s} for s in ("First.", "Second.")]
        self.assertEqual(self.check()[0], "PASS")
        self.review["claims"].reverse()
        with self.assertRaises(ContractError):
            self.check()

    def test_invented_source_ref_revision_field_or_quote_is_rejected(self):
        changes = [{"ref": {**REF, "identity": "other"}}, {"ref": {**REF, "revision": "2"}},
                   {"ref": {**REF, "space": "derived"}}, {"field": "absent"}, {"text": "Invented source"}]
        for change in changes:
            output = deepcopy(self.review)
            output["claims"][0]["sources"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ContractError):
                self.check(output)

    def test_source_quote_existing_but_missing_reported_words_cannot_support_direct_quote(self):
        self.review["claims"][0]["sources"][0]["text"] = "Learner"
        with self.assertRaisesRegex(ContractError, "DirectQuoteNotInCitedSource"):
            self.check()

    def test_pass_needs_source_and_fail_without_source_is_valid(self):
        self.review["claims"][0]["sources"] = []
        with self.assertRaises(ContractError):
            self.check()
        self.review["claims"][0]["status"] = "FAIL"
        next(c for c in self.review["criteria"] if c["id"] == "grounding")["status"] = "FAIL"
        self.assertEqual(self.check()[0], "FAIL")

    def test_unresolved_support_blocks_and_cannot_be_overridden_by_criterion_pass(self):
        self.review["claims"][0]["status"] = "UNRESOLVED"
        with self.assertRaisesRegex(ContractError, "GroundingClaimStatusMismatch"):
            self.check()
        next(c for c in self.review["criteria"] if c["id"] == "grounding")["status"] = "UNRESOLVED"
        self.assertEqual(self.check()[0], "UNRESOLVED")

    def test_existing_quote_does_not_mechanically_prove_speaker_or_entailment(self):
        self.context[0]["content"]["text"] = 'Tutor: "Please explain division."'
        self.review["claims"][0]["sources"][0]["text"] = self.context[0]["content"]["text"]
        # Deliberately unsupported scripted PASS: exact bytes cannot judge attribution.
        self.assertEqual(self.check()[0], "PASS")

    def test_malformed_evidence_fails_closed(self):
        changes = [{"kind": "framing"}, {"sources": {}}, {"status": "MAYBE"},
                   {"rationale": ""}, {"reported_quote": "not in candidate"}]
        for change in changes:
            output = deepcopy(self.review)
            output["claims"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ContractError):
                self.check(output)


class SourceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.h, _, self.runtime, self.token, self.context, _, _ = setup_boundary(
            prepare_candidate=False, protocol_payload=PROTOCOL, destination="https://api.deepseek.com")
        self.payload = {"description": "The work shows a division calculation."}
        self.candidate = self.runtime.propose(self.context, "O", "r1", self.payload)
        self.output = make_review(self.payload, "42 / 6 = 8")

    def execute(self):
        response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(self.output)}}]}
        return self.runtime.validate_with_llm(self.token, self.candidate,
                                             DeepSeekAdapter(LLMConfig("test-key"), Mock(return_value=response)))

    def test_valid_review_commits_and_details_are_rechecked_at_commit(self):
        self.assertEqual(self.context.protocol.revision, "v3")
        review = self.execute()
        altered = deepcopy(self.output)
        altered["claims"][0]["sources"][0]["ref"]["revision"] = "2"
        self.runtime._reviews[review.identity] = replace(review, details_json=json.dumps(altered))
        self.assertEqual(self.runtime.commit(self.token, self.candidate, review.identity).status, "ValidationFailed")
        self.runtime._reviews[review.identity] = review
        self.assertEqual(self.runtime.commit(self.token, self.candidate, review.identity).status, "Committed")

    def test_invented_source_is_logged_and_never_creates_a_passing_review(self):
        self.output["claims"][0]["sources"][0]["text"] = "Invented source words"
        with self.assertRaisesRegex(ContractError, "QuoteNotInExactSource"):
            self.execute()
        self.assertEqual(self.runtime.commit(self.token, self.candidate, "missing").status, "ValidationFailed")
        self.assertIsNone(self.h.get(self.candidate.record.ref))
        self.assertTrue(any(r.kind == "SemanticValidationRejected" for r in self.h.executions.records()))


if __name__ == "__main__":
    unittest.main()
