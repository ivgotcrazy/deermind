from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from urllib.error import URLError
from http.client import RemoteDisconnected, IncompleteRead
import socket
import ssl

from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, LLMConfig, ModelFailure
from foundation.runtime import ContractError
from foundation.source_conflicts import check_absence_review
from run_semantic_stability import load_design, run_suite
from test_source_review import make_review, REF


PROTOCOL = json.loads((Path(__file__).parents[1] / "protocols/observation-smoke-v4.json").read_text(encoding="utf-8"))
QUOTE = "I cannot do division; please explain it."
PAYLOAD = {"description": f'The learner wrote, "{QUOTE}"'}
SOURCE = f'The learner wrote: "{QUOTE}"'


def output(support="text_absent"):
    result = make_review(PAYLOAD, SOURCE, kind="direct_quote", reported_quote=QUOTE)
    claim = result["claims"][0]
    claim.update(support=support, status="PASS" if support == "supported" else "UNRESOLVED" if support == "uncertain" else "FAIL")
    if support in ("text_absent", "uncertain"):
        claim["sources"] = []
    next(c for c in result["criteria"] if c["id"] == "grounding")["status"] = claim["status"]
    return result


def response(value):
    return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(value)}}]}


class AbsenceContractTests(unittest.TestCase):
    def check(self, review, text=SOURCE):
        return check_absence_review(review, PAYLOAD, PROTOCOL["criteria"],
                                    [{"ref": dict(REF), "content": {"text": text}}])

    def test_present_text_contradicts_absence_without_becoming_pass(self):
        raw = output()
        saved = deepcopy(raw)
        status, _, conflicts = self.check(raw)
        self.assertEqual(status, "UNRESOLVED")
        self.assertEqual(raw, saved)
        self.assertEqual(conflicts[0]["matches"][0]["ref"], REF)
        self.assertEqual(conflicts[0]["matches"][0]["text"], SOURCE)

    def test_genuine_absence_remains_fail_and_needs_no_recheck(self):
        status, _, conflicts = self.check(output(), "Only arithmetic")
        self.assertEqual((status, conflicts), ("FAIL", []))

    def test_speaker_mismatch_with_existing_quote_is_still_semantic_fail(self):
        raw = output("speaker_mismatch")
        tutor = SOURCE.replace("learner", "tutor")
        raw["claims"][0]["sources"][0]["text"] = tutor
        self.assertEqual(self.check(raw, tutor)[::2], ("FAIL", []))

    def test_paraphrase_is_not_denied_by_missing_literal_wording(self):
        raw = output()
        raw["claims"][0].update(kind="paraphrase", reported_quote=None)
        with self.assertRaisesRegex(ContractError, "VerbatimAbsenceOnly"):
            self.check(raw)
        raw["claims"][0].update(support="uncertain", status="UNRESOLVED")
        next(c for c in raw["criteria"] if c["id"] == "grounding")["status"] = "UNRESOLVED"
        self.assertEqual(self.check(raw)[0], "UNRESOLVED")

    def test_semantic_denials_require_source_and_status_consistency(self):
        raw = output("meaning_mismatch")
        raw["claims"][0]["sources"] = []
        with self.assertRaisesRegex(ContractError, "SemanticDenialNeedsSource"):
            self.check(raw)
        raw = output("supported")
        raw["claims"][0]["support"] = "text_absent"
        with self.assertRaisesRegex(ContractError, "SupportClassificationStatusMismatch"):
            self.check(raw)


class RecheckTests(unittest.TestCase):
    def setUp(self):
        self.h, self.security, self.r, self.token, self.ctx, _, _ = setup_boundary(
            prepare_candidate=False, protocol_payload=PROTOCOL, destination="https://api.deepseek.com",
            work_payload={"text": SOURCE})
        self.candidate = self.r.propose(self.ctx, "O", "r1", PAYLOAD)

    def adapter(self, *values, budget=2):
        return DeepSeekAdapter(LLMConfig("test-key", max_calls=budget), Mock(side_effect=[
            value if isinstance(value, Exception) else response(value) for value in values]))

    def test_one_recheck_preserves_original_and_links_new_record(self):
        adapter = self.adapter(output(), output("supported"))
        review = self.r.validate_with_llm(self.token, self.candidate, adapter)
        history = self.r.validation_history(self.candidate)
        self.assertEqual([r.status for r in history], ["UNRESOLVED", "PASS"])
        self.assertEqual(json.loads(history[0].details_json), output())
        self.assertEqual(self.h.get(review.execution).payload["previous_review_id"], history[0].identity)
        self.assertEqual(self.r.commit(self.token, self.candidate, history[0].identity).status, "ValidationFailed")
        self.assertEqual(self.r.commit(self.token, self.candidate, review.identity).status, "Committed")
        self.assertEqual(adapter.calls, 2)
        self.assertEqual(adapter.records[1]["purpose"], "ObservationSemanticRecheck")
        second_input = json.loads(adapter.records[1]["messages"][1]["content"])
        self.assertEqual(second_input["source_existence_conflicts"][0]["matches"][0]["text"], SOURCE)

    def test_persistent_conflict_never_loops_even_with_new_adapter(self):
        adapter = self.adapter(output(), output())
        review = self.r.validate_with_llm(self.token, self.candidate, adapter)
        self.assertEqual(review.status, "UNRESOLVED")
        other = self.adapter(output("supported"))
        self.assertEqual(self.r.validate_with_llm(self.token, self.candidate, other), review)
        self.assertEqual(other.calls, 0)
        self.assertEqual(self.r.commit(self.token, self.candidate, review.identity).status, "ValidationFailed")

    def test_recheck_semantic_rejection_is_not_overridden_by_existence(self):
        adapter = self.adapter(output(), output("meaning_mismatch"))
        review = self.r.validate_with_llm(self.token, self.candidate, adapter)
        self.assertEqual(review.status, "FAIL")
        self.assertEqual(self.r.commit(self.token, self.candidate, review.identity).status, "ValidationFailed")

    def test_failed_recheck_or_budget_shortage_preserves_unresolved(self):
        for adapter in (self.adapter(output(), ModelFailure("ProviderTimeout")),
                        self.adapter(output(), budget=1)):
            self.setUp()
            review = self.r.validate_with_llm(self.token, self.candidate, adapter)
            self.assertEqual(review.status, "UNRESOLVED")
            self.assertEqual(len(self.r.validation_history(self.candidate)), 1)
            self.assertTrue(any(r.kind == "SemanticRecheckFailed" for r in self.h.executions.records()))
            self.assertEqual(self.r.commit(self.token, self.candidate, review.identity).status, "ValidationFailed")

    def test_recheck_reauthorizes_context_before_second_model_call(self):
        def first(*args):
            source = self.r.execution("TestRevocation", self.ctx.subject, {})
            self.security.revoke("read-data", source)
            return response(output())
        adapter = DeepSeekAdapter(LLMConfig("test-key"), Mock(side_effect=first))
        review = self.r.validate_with_llm(self.token, self.candidate, adapter)
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(review.status, "UNRESOLVED")
        self.assertEqual(self.r.commit(self.token, self.candidate, review.identity).status, "ValidationFailed")

    def test_initial_transport_failure_does_not_enable_hidden_retry(self):
        adapter = self.adapter(ModelFailure("ProviderTimeout"))
        with self.assertRaises(ModelFailure):
            self.r.validate_with_llm(self.token, self.candidate, adapter)
        with self.assertRaisesRegex(ContractError, "AlreadyAttempted"):
            self.r.validate_with_llm(self.token, self.candidate, adapter)
        self.assertEqual(adapter.calls, 1)

    def test_runner_records_initial_conflict_even_after_successful_recheck(self):
        fixture, _ = load_design("observation-absence-v1.json")
        fixture.update(planned_repetitions=1, planned_model_calls=1, max_model_calls=2,
                       cases=[{"id": "scripted", "work": {"text": SOURCE}, "candidate": PAYLOAD,
                               "expected_status": "PASS", "expected_commit": "Committed", "expected_criteria": {"grounding": "PASS"}}])
        adapter = self.adapter(output(), output("supported"))
        with tempfile.TemporaryDirectory() as directory:
            summary = run_suite(adapter.config, Path(directory), fixture, PROTOCOL, adapter)
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["initial_source_conflicts"], 1)
            self.assertEqual(summary["recheck_calls"], 1)
            self.assertEqual(summary["model_calls"], 2)
            rows = [json.loads(l) for l in (Path(directory) / "evidence.jsonl").read_text().splitlines()]
            self.assertEqual(sum(r["kind"] == "validation_attempt" for r in rows), 2)


class SafeTransportClassificationTests(unittest.TestCase):
    def test_fixed_error_categories_redact_messages_and_never_retry(self):
        for exc, code in [(TimeoutError("secret"), "ProviderTimeout"),
                          (ConnectionResetError("secret"), "ProviderConnectionReset"),
                          (RemoteDisconnected("secret"), "ProviderRemoteDisconnected"),
                          (IncompleteRead(b"secret"), "ProviderIncompleteRead"),
                          (ssl.SSLError("secret"), "ProviderTLSFailure"),
                          (URLError(socket.gaierror("secret")), "ProviderDNSFailure")]:
            with self.subTest(code=code):
                adapter = DeepSeekAdapter(LLMConfig("secret-key"), Mock(side_effect=exc))
                with self.assertRaisesRegex(ModelFailure, code):
                    adapter.complete([], "test")
                self.assertEqual(adapter.calls, 1)
                self.assertNotIn("secret", json.dumps(adapter.records))


if __name__ == "__main__":
    unittest.main()
