"""Mechanical arithmetic and exact runtime binding; scripted labels are not model evidence."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from foundation.candidate_spans import registry
from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, LLMConfig
from foundation.observer_arithmetic import check, evaluate
from foundation.protocol_preflight import check_observation_contract
from foundation.runtime import ContractError
from foundation.source_handles import source_registry
import test_indexed_observation as indexed
from test_structured_output import response

ROOT = Path(__file__).parents[1]
PROTOCOL = json.loads((ROOT / 'protocols/observation-observer-arithmetic-v1.json').read_text(encoding='utf-8'))


def mapped(payload, position='REPORTS_ONLY', tokens=None, **changes):
    ids = [r['handle'] for r in registry(payload)]
    item = {'type': 'ArithmeticEquality', 'span_ids': ids, 'speaker': 'learner', 'sources': ['source_1'],
        'observer_position': position, 'expression_tokens': tokens or ['42', '/', '6'], 'value': '8', 'reason': ''}
    item.update(changes)
    return {'segments': [{'span_ids': ids, 'coverage': 'COMPLETE', 'expressions': [item]}]}


class ObserverArithmeticTests(unittest.TestCase):
    def setUp(self):
        self.payload = {'description': '学习者写下42÷6＝8。'}
        self.sources = source_registry([{'ref': {'space': 'fact', 'identity': 'work', 'revision': '1'},
            'content': {'task': '6kg 苹果42元，15kg多少钱？', 'text': '42÷6＝8。'}}])

    def test_observer_position_controls_arithmetic_not_quoted_speaker(self):
        for speaker in ('learner', 'system', 'other'):
            for position, expected in [('REPORTS_ONLY', 'PASS'), ('AFFIRMS_TRUE', 'FAIL'), ('ASSERTS_FALSE', 'PASS')]:
                with self.subTest(speaker=speaker, position=position):
                    result = check(mapped(self.payload, position, speaker=speaker), self.payload, self.sources)
                    self.assertEqual(result['status'], expected)
                    self.assertFalse(result['checks'][0]['relation_holds'])
                    self.assertEqual(result['checks'][0]['computed'], '7')
                    self.assertTrue(result['mapping_required'])
        self.assertEqual(check(mapped(self.payload, 'ASSERTS_FALSE', value='7'), self.payload, self.sources)['status'], 'FAIL')

    def test_compound_expression_preserves_all_operands_without_learner_intermediate(self):
        payload = {'description': '学习者写下42÷6×15＝120。'}
        out = check(mapped(payload, tokens=['42', '/', '6', '*', '15'], value='120'), payload, self.sources)
        self.assertEqual(len(out['checks']), 1)
        self.assertEqual(out['checks'][0]['expression_tokens'], ['42', '/', '6', '*', '15'])
        self.assertEqual(out['checks'][0]['computed'], '105')
        self.assertEqual(out['status'], 'PASS')

    def test_operator_precedence_associativity_parentheses_and_exact_decimals(self):
        for tokens, expected in [(['0.1', '+', '0.2'], Fraction(3, 10)),
                (['42', '/', '6', '*', '15'], 105), (['8', '/', '2', '/', '2'], 2),
                (['2', '+', '3', '*', '4'], 14), (['(', '2', '+', '3', ')', '*', '-4'], -20)]:
            self.assertEqual(evaluate(tokens), expected)

    def test_invalid_tokens_code_grammar_and_limits_rejected(self):
        for tokens in ([], ['42', '6'], ['1', '+'], ['(', '1'], ['1', ')'], ['__import__("os")'],
                ['1', '/', '0', '+', 'bad'], ['1'] * 65, ['('] * 18 + ['1'] + [')'] * 18):
            with self.subTest(tokens=tokens), self.assertRaises(ContractError):
                evaluate(tokens)
        self.assertIsNone(evaluate(['1', '/', '0', '+', '2']))
        out = mapped(self.payload, 'AFFIRMS_TRUE', tokens=['1', '/', '0'])
        self.assertEqual(check(out, self.payload, self.sources)['status'], 'UNRESOLVED')

    def test_unresolved_scalar_and_unevaluated_remain_distinct(self):
        for kind, tokens, value, pos, status in [
                ('ScalarValue', [], '120', 'REPORTS_ONLY', 'NOT_APPLICABLE'),
                ('UnevaluatedExpression', ['42', '/', '6', '*', '15'], None, 'NO_TRUTH_CLAIM', 'NOT_APPLICABLE'),
                ('UnresolvedNumericMapping', [], None, 'UNRESOLVED', 'UNRESOLVED')]:
            raw = mapped(self.payload, pos, type=kind, expression_tokens=tokens, value=value, reason='Not available.')
            item = check(raw, self.payload, self.sources)['checks'][0]
            self.assertEqual(item['status'], status)
            self.assertIsNone(item['computed'])
        raw = mapped(self.payload, type='ScalarValue')
        with self.assertRaisesRegex(ContractError, 'ScalarCannotCarryEquation'):
            check(raw, self.payload, self.sources)

    def test_exact_sources_coverage_and_required_position_enforced(self):
        for changes in ({'sources': []}, {'sources': ['source_999']}, {'sources': ['source_1', 'source_1']},
                        {'observer_position': 'asserted_true'}, {'span_ids': ['missing']}):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                check(mapped(self.payload, **changes), self.payload, self.sources)
        with self.assertRaises(ContractError):
            check({'segments': []}, self.payload, self.sources)

    def world(self):
        h, s, r, t, ctx, _, _ = setup_boundary(prepare_candidate=False, protocol_payload=PROTOCOL,
            destination='https://api.deepseek.com/beta',
            work_payload={'task': '6kg 苹果42元，15kg多少钱？', 'text': '42÷6＝8。'})
        return h, r, t, r.propose(ctx, 'O', 'r1', self.payload)

    def adapter(self, extraction, mapping='PASS'):
        ids = [r['handle'] for r in registry(self.payload)]
        return DeepSeekAdapter(LLMConfig('OFFLINE', base_url='https://api.deepseek.com/beta', max_calls=3),
            Mock(side_effect=[response({'segments': [{'span_ids': ids, 'role': 'attributed_report',
                'rationale': 'Scripted role.'}]}, 'submit_responsibility'),
                response(extraction, 'submit_extraction'), response(indexed.review(self.payload, mapping=mapping))]))

    def test_shared_runtime_blocks_false_endorsement_and_bad_mapping(self):
        for position, mapping, expected in [('REPORTS_ONLY', 'PASS', True), ('AFFIRMS_TRUE', 'PASS', False),
                ('REPORTS_ONLY', 'FAIL', False), ('REPORTS_ONLY', 'UNRESOLVED', False)]:
            with self.subTest(position=position, mapping=mapping):
                h, r, token, candidate = self.world()
                result = r.validate_with_llm(token, candidate, self.adapter(mapped(self.payload, position), mapping))
                self.assertEqual(r.commit(token, candidate, result.identity).status == 'Committed', expected)
                self.assertEqual(h.get(candidate.record.ref) is not None, expected)

    def test_commit_recomputes_and_binds_arithmetic_to_exact_candidate(self):
        h, r, token, candidate = self.world()
        result = r.validate_with_llm(token, candidate, self.adapter(mapped(self.payload)))
        ref = r._arithmetic_executions[candidate.identity]
        original = h.get(ref).payload
        for key in ('extraction', 'result'):
            wrong = deepcopy(original)
            if key == 'extraction':
                wrong[key]['segments'][0]['expressions'][0]['observer_position'] = 'AFFIRMS_TRUE'
            else:
                wrong[key]['checks'][0]['computed'] = '8'
            forged = r.execution('ArithmeticExtractionExecution', 'learner-A', wrong)
            with self.assertRaises(ContractError):
                r._checked_arithmetic(candidate, forged)
        self.assertEqual(r.commit(token, candidate, result.identity).status, 'Committed')

    def test_new_profile_is_opt_in_and_compatible_old_contracts_still_pass(self):
        self.assertEqual(check_observation_contract(PROTOCOL)['status'], 'PASS')
        for name in ('observation-validation-v14.json', 'observation-feasibility-v1.json'):
            old = json.loads((ROOT / 'protocols' / name).read_text(encoding='utf-8'))
            self.assertEqual(check_observation_contract(old)['status'], 'PASS')
        wrong = deepcopy(PROTOCOL)
        wrong['arithmetic_extraction_format'] = 'typed-expressions-v2'
        with self.assertRaisesRegex(ValueError, 'ExpressionContractMismatch'):
            check_observation_contract(wrong)


if __name__ == '__main__':
    unittest.main()
