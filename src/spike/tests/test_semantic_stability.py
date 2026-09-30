import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from foundation.llm import DeepSeekAdapter, LLMConfig, ModelFailure
from run_semantic_stability import load_design, run_suite, schedule, summarize


FIXTURE, PROTOCOL = load_design()


def response_for(case, reject_all=False):
    output = {"reviewed_fields": ["description"], "criteria": [
        {"id": criterion["id"], "status": "FAIL" if reject_all else case["expected_criteria"].get(criterion["id"], "PASS"),
         "quotes": [{"field": "description", "text": case["candidate"]["description"]}],
         "rationale": "Offline structural test decision."}
        for criterion in PROTOCOL["criteria"]]}
    return {"model": "mock", "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(output)}}]}


class StabilityTests(unittest.TestCase):
    def test_schedule_has_five_executions_per_case_and_is_fixed(self):
        entries = schedule(FIXTURE)
        self.assertEqual(entries, schedule(FIXTURE))
        self.assertEqual(len(entries), 40)
        for case in FIXTURE["cases"]:
            self.assertEqual([n for c, n in entries if c["id"] == case["id"]], [1, 2, 3, 4, 5])

    def test_attribution_pair_changes_only_source_not_candidate(self):
        cases = {c["id"]: c for c in FIXTURE["cases"]}
        positive = cases["attributed_self_report_positive"]
        negative = cases["fabricated_attribution_negative"]
        self.assertEqual(positive["candidate"], negative["candidate"])
        self.assertNotEqual(positive["work"], negative["work"])
        self.assertEqual(positive["expected_status"], "PASS")
        self.assertEqual(negative["expected_status"], "FAIL")

    def test_small_budget_is_rejected_without_resetting_adapter_or_making_calls(self):
        adapter = DeepSeekAdapter(LLMConfig("test-key"), Mock())
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Budget below"):
                run_suite(adapter.config, Path(directory), FIXTURE, PROTOCOL, adapter)
        adapter.transport.assert_not_called()

    def test_all_results_are_retained_and_expected_labels_are_not_model_inputs(self):
        config = LLMConfig("test-key", max_calls=40)
        adapter = DeepSeekAdapter(config, Mock(side_effect=[response_for(c) for c, _ in schedule(FIXTURE)]))
        with tempfile.TemporaryDirectory() as directory:
            summary = run_suite(config, Path(directory), FIXTURE, PROTOCOL, adapter)
            saved = json.loads((Path(directory) / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary, saved)
            self.assertEqual(summary["matched_runs"], 40)
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["positive_runs_planned"], 15)
            self.assertEqual(summary["negative_runs_planned"], 25)
            for record in adapter.records:
                user_payload = json.loads(record["messages"][1]["content"])
                self.assertEqual(set(user_payload), {"context", "candidate", "arithmetic_fixture", "criteria"})
                self.assertNotIn("expected_status", json.dumps(record["messages"]))
            rows = [json.loads(line) for line in (Path(directory) / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(sum(row["kind"] == "model_execution" for row in rows), 40)
            self.assertEqual(sum(row["kind"] == "case_result" for row in rows), 40)

    def test_reject_all_cannot_be_reported_as_success(self):
        config = LLMConfig("test-key", max_calls=40)
        adapter = DeepSeekAdapter(config, Mock(side_effect=[response_for(c, True) for c, _ in schedule(FIXTURE)]))
        with tempfile.TemporaryDirectory() as directory:
            summary = run_suite(config, Path(directory), FIXTURE, PROTOCOL, adapter)
        self.assertEqual(summary["false_negatives"], 15)
        self.assertEqual(summary["status"], "NON_SUCCESS")
        self.assertEqual(summary["matched_runs"], 25)

    def test_interrupted_run_keeps_completed_evidence_and_reports_remaining(self):
        config = LLMConfig("test-key", max_calls=40)
        adapter = DeepSeekAdapter(config, Mock(side_effect=[response_for(c) for c, _ in schedule(FIXTURE)]))
        def stop(summary):
            raise RuntimeError("test interruption")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "test interruption"):
                run_suite(config, Path(directory), FIXTURE, PROTOCOL, adapter, stop)
            summary = json.loads((Path(directory) / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["completed_runs"], 1)
            self.assertEqual(summary["not_run"], 39)
            rows = [json.loads(line) for line in (Path(directory) / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(sum(r["kind"] == "model_execution" for r in rows), 1)

    def test_statistics_do_not_hide_unknowns_or_count_them_as_correct_rejections(self):
        results = [
            {"case_id": "final_omission_negative", "result": "INCONCLUSIVE", "semantic_status": "UNRESOLVED"},
            {"case_id": "paraphrase_positive", "result": "INCONCLUSIVE", "failure_type": "ModelFailure"},
            {"case_id": "latent_ability_negative", "result": "FAIL", "semantic_status": "PASS", "false_positive": True},
            {"case_id": "chinese_positive", "result": "FAIL", "semantic_status": "FAIL", "false_negative": True},
        ]
        summary = summarize(results, FIXTURE, 4)
        self.assertEqual(summary["matched_runs"], 0)
        self.assertEqual(summary["unresolved_reviews"], 1)
        self.assertEqual(summary["protocol_or_runtime_failures"], 1)
        self.assertEqual(summary["false_positives"], 1)
        self.assertEqual(summary["false_negatives"], 1)
        self.assertEqual(summary["not_run"], 36)


if __name__ == "__main__":
    unittest.main()
