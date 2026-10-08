"""Representation, exact binding and admission tests; no semantic ability claim."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from foundation.candidate_spans import (registry, span, partition, expand_classification,
                                       expand_review, bind_contract)
from foundation.expressions import extraction_contract_v2, check_expression_extraction_v2
from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, LLMConfig, ModelFailure
from foundation.protocol_preflight import check_observation_contract
from foundation.records import json_value
from foundation.runtime import ContractError
from foundation.source_handles import source_registry
from foundation.structured_output import matches_schema
from test_structured_output import response

ROOT = Path(__file__).parents[1]
PROTOCOL = json.loads((ROOT / 'protocols/observation-validation-v14.json').read_text(encoding='utf-8'))


def extraction(payload, kind='ScalarValue', **values):
    ids = [r['handle'] for r in registry(payload)]
    item = {'type': kind, 'span_ids': ids, 'speaker': 'learner', 'sources': ['source_1'],
            'stance': 'reported_only', 'operator': None, 'left': None, 'right': None,
            'value': '120' if kind == 'ScalarValue' else None, 'reason': ''}
    item.update(values)
    return {'segments': [{'span_ids': ids, 'coverage': 'COMPLETE', 'expressions': [item]}]}


def review(payload, mapping='PASS', final='PASS'):
    ids = [r['handle'] for r in registry(payload)]
    return {'reviewed_fields': ['description'],
        'criteria': [{'id': c['id'], 'status': mapping if c['id']=='arithmetic_mapping' else
                     final if c['id']=='final_result' else 'PASS',
                     'quotes': [{'span_ids': ids}], 'rationale': 'Explicit scripted test judgment.'}
                     for c in PROTOCOL['criteria']],
        'claims': [{'span_ids': ids, 'kind': 'paraphrase', 'reported_quote': None,
            'status': 'PASS', 'sources': ['source_1'], 'rationale': 'Explicit scripted test judgment.',
            'support': 'supported', 'inspection_scope': 'COMPLETE_CONTEXT',
            'attribution': {'speaker': 'learner', 'stance': 'reported'}, 'boundary_status': 'PASS'}]}


class IndexedObservationTests(unittest.TestCase):
    def setUp(self):
        self.payload = {'description': '学习者算出了120。'}
        self.sources = source_registry([{'ref': {'space': 'fact', 'identity': 'work', 'revision': '1'},
            'content': {'task': '6kg苹果42元，15kg多少钱？', 'text': '42÷6＝8，8×15＝120。指出步骤，不给结果。'}}])

    def compute(self, value, payload=None):
        return check_expression_extraction_v2(value, payload or self.payload, self.sources)

    def world(self, payload=None):
        h,s,r,t,ctx,_,_=setup_boundary(prepare_candidate=False, protocol_payload=PROTOCOL,
            destination='https://api.deepseek.com/beta',
            work_payload={'task': '6kg苹果42元，15kg多少钱？', 'text': '42÷6＝8，8×15＝120。指出步骤，不给结果。'})
        return h,s,r,t,ctx,r.propose(ctx,'O','r1',payload or self.payload)

    def adapter(self, payload=None, *, mapped=None, raw=None):
        payload=payload or self.payload
        ids=[r['handle'] for r in registry(payload)]
        return DeepSeekAdapter(LLMConfig('OFFLINE', base_url='https://api.deepseek.com/beta',max_calls=3),
            Mock(side_effect=[response({'segments':[{'span_ids':ids, 'role':'attributed_report',
                'rationale':'Explicit scripted test label.'}]},'submit_responsibility'),
                response(mapped or extraction(payload),'submit_extraction'),response(raw or review(payload))]))

    def test_registry_is_lossless_for_punctuation_whitespace_decimals_and_repeated_text(self):
        for text in ('\n 结果7.5；结果7.5。\n', '42÷6＝7，42÷6＝7。', '不含标点', 'a\n\nb'):
            rows=registry({'description':text})
            self.assertEqual(''.join(r['text'] for r in rows),text)
            for r in rows:self.assertEqual(text[r['start']:r['end']],r['text'])
            self.assertEqual(span([r['handle'] for r in rows],rows)['text'],text)

    def test_occurrence_selected_by_handle_not_ambiguous_substring_search(self):
        payload={'description':'42÷6＝7；42÷6＝7；'}
        rows=registry(payload)
        self.assertEqual(rows[0]['text'],rows[1]['text'])
        self.assertNotEqual(span([rows[0]['handle']],rows)['start'],span([rows[1]['handle']],rows)['start'])
        value=extraction(payload,'NumericAssertion',operator='divide',left='42',right='6',value='7')
        value['segments'][0]['expressions'][0]['span_ids']=[rows[1]['handle']]
        checked=self.compute(value,payload)['checks'][0]
        self.assertEqual(checked['start'],rows[1]['start'])

    def test_unknown_reordered_disjoint_duplicate_and_cross_field_handles_rejected(self):
        rows=registry({'a':'one,two,three','b':'four'})
        for ids in ([],['missing'],['candidate_0','candidate_0'],['candidate_1','candidate_0'],
                    ['candidate_0','candidate_2'],['candidate_2','candidate_3']):
            with self.subTest(ids=ids), self.assertRaises(ContractError):span(ids,rows)

    def test_coverage_gaps_overlaps_and_text_injection_are_rejected(self):
        payload={'description':'第一句。第二句。'}
        for rows in ([{'span_ids':['candidate_1']}], [{'span_ids':['candidate_0']}],
                     [{'span_ids':['candidate_0']},{'span_ids':['candidate_0','candidate_1']}]):
            with self.assertRaises(ContractError):partition(rows,payload,registry(payload))
        raw=review(payload);raw['claims'][0]['text']='替换后的文本'
        with self.assertRaises(ContractError):expand_review(raw,payload)

    def test_scalar_is_representable_without_inventing_operation_or_truth_approval(self):
        value=extraction(self.payload)
        self.assertTrue(matches_schema(value,extraction_contract_v2()['parameters']))
        checked=self.compute(value)['checks'][0]
        self.assertEqual(checked['value'],'120');self.assertIsNone(checked['computed'])
        self.assertEqual(checked['status'],'NOT_APPLICABLE')
        for changes in ({'operator':'add'},{'left':'0'},{'value':None}):
            wrong=deepcopy(value);wrong['segments'][0]['expressions'][0].update(changes)
            self.assertFalse(matches_schema(wrong,extraction_contract_v2()['parameters']))

    def test_equation_requires_all_operands_and_result_at_schema_boundary(self):
        value=extraction(self.payload,'NumericAssertion',operator='divide',left='42',right='6',value='8')
        for key in ('operator','left','right','value'):
            wrong=deepcopy(value);wrong['segments'][0]['expressions'][0][key]=None
            self.assertFalse(matches_schema(wrong,extraction_contract_v2()['parameters']))
        self.assertEqual(self.compute(value)['status'],'PASS')  # Explicit reporting label.
        value['segments'][0]['expressions'][0]['stance']='asserted_true'
        self.assertEqual(self.compute(value)['status'],'FAIL')
        value['segments'][0]['expressions'][0]['stance']='asserted_false'
        self.assertEqual(self.compute(value)['status'],'PASS')

    def test_operation_without_result_stays_unevaluated(self):
        value=extraction(self.payload,'UnevaluatedExpression',operator='multiply',left='42',right='15')
        checked=self.compute(value)['checks'][0]
        self.assertIsNone(checked['computed']);self.assertIsNone(checked['value'])
        value['segments'][0]['expressions'][0]['value']='630'
        with self.assertRaises(ContractError):self.compute(value)

    def test_unresolved_unknowns_bad_numbers_and_invalid_source_do_not_pass(self):
        value=extraction(self.payload,'UnresolvedNumericMapping',reason='Cannot resolve asserted relation.')
        self.assertEqual(self.compute(value)['status'],'UNRESOLVED')
        for changes in ({'value':'?'},{'sources':[]},{'sources':['source_999']},{'sources':['source_1','source_1']}):
            value=extraction(self.payload);value['segments'][0]['expressions'][0].update(changes)
            with self.assertRaises(ContractError):self.compute(value)

    def test_dynamic_contract_restricts_candidate_and_source_handles(self):
        contract=bind_contract(extraction_contract_v2(),registry(self.payload),self.sources)['parameters']
        value=extraction(self.payload)
        self.assertTrue(matches_schema(value,contract))
        value['segments'][0]['expressions'][0]['sources']=['source_999']
        self.assertFalse(matches_schema(value,contract))

    def test_source_quotes_and_responsibility_text_expand_without_recopy(self):
        rows=registry(self.payload);ids=[r['handle'] for r in rows]
        value=expand_classification({'segments':[{'span_ids':ids,'role':'attributed_report','rationale':'Test.'}]},self.payload)
        self.assertEqual(value['segments'][0]['text'],self.payload['description'])
        expanded=expand_review(review(self.payload),self.payload)
        self.assertEqual(expanded['claims'][0]['text'],self.payload['description'])
        self.assertEqual(expanded['criteria'][0]['quotes'][0],{'field':'description','text':self.payload['description']})

    def test_runtime_semantic_rejection_still_blocks_scalar_or_missing_mapping(self):
        for mapping,final in [('FAIL','PASS'),('UNRESOLVED','PASS'),('PASS','FAIL')]:
            h,s,r,t,ctx,c=self.world()
            raw=review(self.payload,mapping=mapping,final=final)
            result=r.validate_with_llm(t,c,self.adapter(raw=raw))
            self.assertNotEqual(result.status,'PASS')
            self.assertEqual(r.commit(t,c,result.identity).status,'ValidationFailed')
            self.assertIsNone(h.get(c.record.ref))

    def test_exact_binding_and_commit_recompute_indexed_wire(self):
        h,s,r,t,ctx,c=self.world();a=self.adapter();result=r.validate_with_llm(t,c,a)
        self.assertEqual(r.commit(t,c,result.identity).status,'Committed')
        record=h.get(result.execution).payload
        self.assertEqual(record['candidate_registry'],registry(self.payload))
        self.assertIn('span_ids',record['wire_output']['claims'][0])
        self.assertEqual(record['details']['claims'][0]['text'],self.payload['description'])
        self.assertEqual(a.calls,3)
        other=r.propose(ctx,'O','r2',{'description':'Different candidate'})
        with self.assertRaisesRegex(ContractError,'BindingMismatch'):
            r._checked_arithmetic(other,r._arithmetic_executions[c.identity])

    def test_tampered_registry_and_computation_cannot_reuse_pass_review(self):
        from dataclasses import replace
        for target in ('registry','computation'):
            h,s,r,t,ctx,c=self.world();result=r.validate_with_llm(t,c,self.adapter())
            payload=h.get(result.execution).payload
            if target=='registry':payload['candidate_registry'][0]['text']='Forged'
            else:payload['arithmetic_result']['checks'][0]['value']='999'
            forged=r.execution('SemanticValidationExecution',ctx.subject,payload)
            altered=replace(result,execution=forged)
            r._reviews[result.identity]=altered
            self.assertNotEqual(r.commit(t,c,result.identity).status,'Committed')

    def test_new_protocol_requires_matching_locator_and_expression_profiles(self):
        self.assertEqual(check_observation_contract(PROTOCOL)['status'],'PASS')
        for key,value in [('candidate_encoding',None),('arithmetic_extraction_format','typed-expressions-v1')]:
            bad=deepcopy(PROTOCOL);bad[key]=value
            with self.assertRaises(ValueError):check_observation_contract(bad)


if __name__=='__main__':unittest.main()
