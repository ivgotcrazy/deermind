from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, LLMConfig, ModelFailure
from foundation.structured_output import check_schema, matches_schema
from run_semantic_stability import load_design, run_suite
from test_arithmetic import PAYLOAD, extraction, passing_review


FIXTURE, PROTOCOL = load_design("observation-structured-v1.json")
CONTRACTS = PROTOCOL["output_contracts"]
CONFIG = LLMConfig("test-secret", base_url="https://api.deepseek.com/beta", max_calls=48)


def response(value, name="submit_review"):
    return {"choices": [{"finish_reason": "tool_calls", "message": {
        "content": None, "reasoning_content": "private hidden text",
        "tool_calls": [{"id": "test-call", "type": "function", "function": {
            "name": name, "arguments": json.dumps(value)}}]}}]}


class StructuredOutputTests(unittest.TestCase):
    def test_contracts_validate_nullable_quotes_and_reject_shape_or_enum_changes(self):
        for contract in CONTRACTS.values():
            check_schema(contract["parameters"])
        schema = CONTRACTS["validation"]["parameters"]
        good = passing_review()
        self.assertTrue(matches_schema(good, schema))
        self.assertIsNone(good["claims"][0]["reported_quote"])
        for mutate in (lambda r: r["claims"][0].pop("sources"),
                       lambda r: r["claims"][0].update(unexpected=True),
                       lambda r: r["criteria"][0].update(status="APPROVED"),
                       lambda r: r["claims"][0].update(reported_quote=3)):
            bad = deepcopy(good)
            mutate(bad)
            self.assertFalse(matches_schema(bad, schema))

    def test_forced_strict_envelope_retains_arguments_without_dispatch_or_secrets(self):
        transport = Mock(return_value=response(passing_review()))
        adapter = DeepSeekAdapter(CONFIG, transport)
        output, _ = adapter.complete([], "test", output_contract=CONTRACTS["validation"])
        self.assertEqual(output, passing_review())
        url, _, wire, _ = transport.call_args.args
        self.assertEqual(url, CONFIG.base_url + "/chat/completions")
        self.assertEqual(wire["tool_choice"], {"type": "function", "function": {"name": "submit_review"}})
        self.assertTrue(wire["tools"][0]["function"]["strict"])
        self.assertNotIn("response_format", wire)
        self.assertEqual(wire["thinking"], {"type": "disabled"})
        saved = json.dumps(adapter.records)
        self.assertNotIn("test-secret", saved)
        self.assertNotIn("private hidden text", saved)
        self.assertEqual(adapter.records[0]["tool_calls"][0]["function"]["arguments"], json.dumps(output))

    def test_invalid_envelopes_json_and_schema_fail_without_retry_or_fallback(self):
        good = response(passing_review())
        changes = [
            lambda c: c.update(finish_reason="stop"),
            lambda c: c["message"].update(tool_calls=[]),
            lambda c: c["message"]["tool_calls"].append(deepcopy(c["message"]["tool_calls"][0])),
            lambda c: c["message"]["tool_calls"][0]["function"].update(name="execute_shell"),
            lambda c: c["message"].update(content="unstructured answer"),
            lambda c: c["message"]["tool_calls"][0]["function"].update(arguments='{"field":"text":"bad"}'),
            lambda c: c["message"]["tool_calls"][0]["function"].update(arguments='{"x":1,"x":2}'),
            lambda c: c["message"]["tool_calls"][0]["function"].update(arguments='{}'),
        ]
        for change in changes:
            with self.subTest(change=change):
                bad = deepcopy(good)
                change(bad["choices"][0])
                adapter = DeepSeekAdapter(CONFIG, Mock(return_value=bad))
                with self.assertRaises(ModelFailure):
                    adapter.complete([], "test", output_contract=CONTRACTS["validation"])
                self.assertEqual(adapter.calls, 1)
                self.assertEqual(adapter.records[0]["status"], "FAILED")
                adapter.transport.assert_called_once()

    def test_wrong_endpoint_and_unsupported_contract_stop_before_transport(self):
        adapter = DeepSeekAdapter(replace(CONFIG, base_url="https://api.deepseek.com"), Mock())
        with self.assertRaisesRegex(ModelFailure, "EndpointMismatch"):
            adapter.complete([], "test", output_contract=CONTRACTS["validation"])
        adapter.transport.assert_not_called()
        adapter = DeepSeekAdapter(CONFIG, Mock())
        bad = deepcopy(CONTRACTS["validation"])
        bad["parameters"]["additionalProperties"] = True
        with self.assertRaisesRegex(ModelFailure, "InvalidOutputContract"):
            adapter.complete([], "test", output_contract=bad)
        self.assertEqual(adapter.calls, 0)

    def test_same_cases_labels_order_and_semantic_rules_as_v6(self):
        old_fixture, old_protocol = load_design("observation-arithmetic-v1.json")
        for key in ("cases", "schedule_seed", "planned_repetitions", "planned_model_calls", "initial_model_calls", "max_model_calls"):
            self.assertEqual(FIXTURE[key], old_fixture[key])
        for key in ("criteria", "validation_format"):
            self.assertEqual(PROTOCOL[key], old_protocol[key])
        for key in ("generation_system", "validation_system", "extraction_system"):
            self.assertEqual(PROTOCOL[key].split("\nDELIVERY:")[0], old_protocol[key])

    def test_runtime_still_blocks_structurally_valid_false_semantic_pass(self):
        h, _, runtime, token, ctx, _, _ = setup_boundary(
            prepare_candidate=False, protocol_payload=PROTOCOL, destination=CONFIG.base_url)
        candidate = runtime.propose(ctx, "O", "r1", PAYLOAD)
        adapter = DeepSeekAdapter(CONFIG, Mock(side_effect=[
            response(extraction(), "submit_extraction"), response(passing_review())]))
        review = runtime.validate_with_llm(token, candidate, adapter)
        self.assertEqual(h.get(review.execution).payload["semantic_status"], "PASS")
        self.assertEqual(review.status, "FAIL")
        self.assertEqual(runtime.commit(token, candidate, review.identity).status, "ValidationFailed")
        self.assertEqual([r["output_contract"]["name"] for r in adapter.records], ["submit_extraction", "submit_review"])

    def test_provider_schema_rejection_stops_batch_with_remaining_cases_unrun(self):
        adapter = DeepSeekAdapter(CONFIG, Mock(side_effect=ModelFailure("ProviderHTTPError:400")))
        with tempfile.TemporaryDirectory() as directory:
            summary = run_suite(CONFIG, Path(directory), FIXTURE, PROTOCOL, adapter)
            saved = json.loads((Path(directory) / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, summary)
        self.assertEqual(summary["completed_runs"], 1)
        self.assertEqual(summary["not_run"], 15)
        self.assertEqual(summary["protocol_or_runtime_failures"], 1)
        self.assertEqual(summary["matched_runs"], 0)
        self.assertEqual(summary["model_calls"], 1)
        self.assertEqual(summary["status"], "NON_SUCCESS")

    def test_batch_wrong_endpoint_rejects_before_any_calls(self):
        config = replace(CONFIG, base_url="https://api.deepseek.com")
        adapter = DeepSeekAdapter(config, Mock())
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "ProtocolProviderEndpointMismatch"):
                run_suite(config, Path(directory), FIXTURE, PROTOCOL, adapter)
        adapter.transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
