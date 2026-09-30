from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, LLMConfig, ModelFailure, load_config
from foundation.runtime import ContractError
from foundation.security import AccessDenied


def response(content, finish="stop"):
    return {"id": "provider-test-response", "model": "deepseek-flash",
            "system_fingerprint": "test-fingerprint", "usage": {"total_tokens": 10},
            "choices": [{"finish_reason": finish, "message": {"content": content,
                         "reasoning_content": "must never appear in retained evidence"}}]}


class AdapterTests(unittest.TestCase):
    def test_load_config_preserves_environment_precedence_and_redacts_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text('DEERMIND_LLM_API_KEY="file-test-key"\nDEERMIND_LLM_MAX_CALLS=7\n', encoding="utf-8")
            config = load_config(root, {"DEERMIND_LLM_API_KEY": "environment-test-key"})
            self.assertEqual(config.api_key, "environment-test-key")
            self.assertEqual(config.max_calls, 7)
            self.assertNotIn("environment-test-key", repr(config))
            self.assertNotIn("environment-test-key", json.dumps(config.public()))

    def test_invalid_endpoint_and_budget_are_rejected(self):
        for kwargs in ({"base_url": "http://api.deepseek.com"}, {"base_url": "https://user:secret@example.com"},
                       {"max_calls": 0}, {"timeout_seconds": float("nan")}, {"max_output_tokens": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                LLMConfig("test-key", **kwargs)

    def test_missing_key_and_call_budget_stop_before_transport(self):
        transport = Mock(return_value=response('{"description":"result"}'))
        adapter = DeepSeekAdapter(LLMConfig(""), transport)
        with self.assertRaisesRegex(ModelFailure, "MissingAPIKey"):
            adapter.complete([], "test")
        transport.assert_not_called()
        adapter = DeepSeekAdapter(LLMConfig("test-key", max_calls=1), transport)
        adapter.complete([], "test")
        with self.assertRaisesRegex(ModelFailure, "BudgetExhausted"):
            adapter.complete([], "test")
        self.assertEqual(transport.call_count, 1)

    def test_wire_contract_and_evidence_omit_key_and_reasoning_content(self):
        transport = Mock(return_value=response('{"description":"result"}'))
        adapter = DeepSeekAdapter(LLMConfig("local-test-secret"), transport)
        result, execution = adapter.complete([{"role": "user", "content": "JSON please"}], "test")
        self.assertEqual(result, {"description": "result"})
        args = transport.call_args.args
        self.assertEqual(args[0], "https://api.deepseek.com/chat/completions")
        self.assertEqual(args[2]["response_format"], {"type": "json_object"})
        self.assertEqual(args[2]["thinking"], {"type": "disabled"})
        saved = json.dumps(adapter.records)
        self.assertNotIn("local-test-secret", saved)
        self.assertNotIn("must never appear", saved)
        self.assertEqual(adapter.records[0]["execution_id"], execution)

    def test_empty_truncated_invalid_duplicate_and_nonfinite_outputs_are_failures(self):
        for content, finish in (("", "stop"), ('{"description":"partial"}', "length"), ("not JSON", "stop"),
                                ("[]", "stop"), ('{"x":NaN}', "stop"), ('{"x":1,"x":2}', "stop")):
            with self.subTest(content=content):
                adapter = DeepSeekAdapter(LLMConfig("test-key"), Mock(return_value=response(content, finish)))
                with self.assertRaises(ModelFailure):
                    adapter.complete([], "test")
                self.assertEqual(adapter.records[0]["status"], "FAILED")
                self.assertEqual(adapter.calls, 1)

    def test_provider_failure_does_not_retry_or_echo_transport_secrets(self):
        transport = Mock(side_effect=RuntimeError("secret-in-error"))
        adapter = DeepSeekAdapter(LLMConfig("test-key"), transport)
        with self.assertRaisesRegex(ModelFailure, "ProviderTransportFailure"):
            adapter.complete([], "test")
        self.assertEqual(transport.call_count, 1)
        self.assertNotIn("secret-in-error", json.dumps(adapter.records))


class LLMBoundaryTests(unittest.TestCase):
    def setUp(self):
        protocol = json.loads((Path(__file__).parents[1] / "protocols" / "observation-smoke-v1.json").read_text(encoding="utf-8"))
        self.h, self.s, self.r, self.token, self.ctx, _, _ = setup_boundary(
            prepare_candidate=False, protocol_payload=protocol, destination="https://api.deepseek.com")

    def adapter(self, review_status="PASS"):
        transport = Mock(side_effect=[response('{"description":"42 / 6 = 8 is a division mismatch."}'),
                                      response(json.dumps({"status": review_status, "rationale": "mock transport control"}))])
        return DeepSeekAdapter(LLMConfig("test-key"), transport)

    def test_two_independent_calls_bind_review_to_candidate_before_commit(self):
        adapter = self.adapter()
        candidate = self.r.generate_with_llm(self.token, self.ctx, adapter)
        self.assertIsNone(self.h.get(candidate.record.ref))
        review = self.r.validate_with_llm(self.token, candidate, adapter)
        self.assertFalse(review.fixture)
        self.assertNotEqual(adapter.records[0]["execution_id"], adapter.records[1]["execution_id"])
        self.assertEqual(self.r.commit(self.token, candidate, review.identity).status, "Committed")
        self.assertNotIn("untrusted_for_observation", json.dumps(adapter.records))

    def test_review_unresolved_blocks_standing(self):
        adapter = self.adapter("UNRESOLVED")
        candidate = self.r.generate_with_llm(self.token, self.ctx, adapter)
        review = self.r.validate_with_llm(self.token, candidate, adapter)
        self.assertEqual(self.r.commit(self.token, candidate, review.identity).status, "ValidationFailed")
        self.assertIsNone(self.h.get(candidate.record.ref))

    def test_destination_mismatch_or_revoked_data_permission_prevents_model_call(self):
        adapter = self.adapter()
        adapter.config = replace(adapter.config, base_url="https://different-provider.example")
        with self.assertRaisesRegex(ContractError, "ModelDestinationMismatch"):
            self.r.generate_with_llm(self.token, self.ctx, adapter)
        self.assertEqual(adapter.calls, 0)
        adapter = self.adapter()
        source = self.r.execution("TestControl", self.ctx.subject, {})
        self.s.revoke("read-data", source)
        with self.assertRaises(AccessDenied):
            self.r.generate_with_llm(self.token, self.ctx, adapter)
        self.assertEqual(adapter.calls, 0)

    def test_network_failure_preserves_failed_execution_and_no_state(self):
        adapter = DeepSeekAdapter(LLMConfig("test-key"), Mock(side_effect=ModelFailure("ProviderHTTPError:503")))
        with self.assertRaises(ModelFailure):
            self.r.generate_with_llm(self.token, self.ctx, adapter)
        self.assertEqual(len(self.h.states.records()), 1)  # Only original B-old fixture.
        self.assertTrue(any(r.kind == "LLMGenerationFailed" for r in self.h.executions.records()))


if __name__ == "__main__":
    unittest.main()
