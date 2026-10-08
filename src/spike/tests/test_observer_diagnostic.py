"""Fault injection provenance and mandatory mapping-review behavior."""
from copy import deepcopy
import json
import unittest
from unittest.mock import Mock

from foundation.candidate_spans import registry
from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, LLMConfig
from run_observer_arithmetic import DiagnosticAdapter, load_plan
from test_observer_arithmetic import PROTOCOL
from test_structured_output import response
import test_indexed_observation as indexed


class ObserverDiagnosticTests(unittest.TestCase):
    def test_injected_mapping_is_not_a_provider_call_and_mandatory_review_blocks_both_directions(self):
        plan = load_plan()
        for spec in plan['cases'][-2:]:
            with self.subTest(case=spec['id']):
                payload = spec['candidate']
                ids = [r['handle'] for r in registry(payload)]
                transport = Mock(side_effect=[response({'segments': [{'span_ids': ids,
                    'role': 'attributed_report', 'rationale': 'Scripted.'}]}, 'submit_responsibility'),
                    response(indexed.review(payload, mapping='FAIL'))])
                adapter = DeepSeekAdapter(LLMConfig('OFFLINE', base_url='https://api.deepseek.com/beta', max_calls=2), transport)
                proxy = DiagnosticAdapter(adapter, spec)
                h, s, r, token, ctx, _, _ = setup_boundary(prepare_candidate=False,
                    protocol_payload=PROTOCOL, destination=adapter.config.base_url,
                    work_payload={'task': '6kg 苹果42元，15kg多少钱？', 'text': spec['input']})
                candidate = r.propose(ctx, 'O', 'r1', payload)
                result = r.validate_with_llm(token, candidate, proxy)
                self.assertNotEqual(result.status, 'PASS')
                self.assertNotEqual(r.commit(token, candidate, result.identity).status, 'Committed')
                self.assertEqual(adapter.calls, 2)
                self.assertEqual(len(proxy.injections), 1)
                self.assertFalse(proxy.injections[0]['provider_call'])
                execution = h.get(r._arithmetic_executions[candidate.identity]).payload
                self.assertTrue(execution['model_call'].startswith('SCRIPTED-MAPPING-FAULT-'))
                self.assertEqual(execution['result']['status'], spec['expected_arithmetic'])
                for record in adapter.records:
                    sent = json.dumps(record['messages'])
                    self.assertNotIn('expected_mapping', sent)
                    self.assertNotIn('injected_observer_position', sent)

    def test_normal_extraction_is_forwarded_without_rewriting(self):
        adapter = Mock()
        adapter.complete.return_value = ({'raw': 'untouched'}, 'call-1')
        spec = load_plan()['cases'][0]
        proxy = DiagnosticAdapter(adapter, spec)
        messages, contract = [{'role': 'user', 'content': 'original'}], {'name': 'example'}
        self.assertEqual(proxy.complete(messages, 'ArithmeticExtraction', output_contract=contract),
                         ({'raw': 'untouched'}, 'call-1'))
        adapter.complete.assert_called_once_with(messages, 'ArithmeticExtraction', output_contract=contract)
        self.assertEqual(proxy.injections, [])


if __name__ == '__main__':
    unittest.main()
