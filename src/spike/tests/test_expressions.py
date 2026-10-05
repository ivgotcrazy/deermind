"""Local typed-mapping fixtures; scripted reviewers never establish semantic quality."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from foundation.arithmetic import check_arithmetic_extraction
from foundation.cases import EvidenceRecorder
from foundation.expressions import check_expression_extraction
from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, LLMConfig, ModelFailure
from foundation.protocol_preflight import check_observation_contract
from foundation.records import json_value
from foundation.runtime import ContractError
from foundation.source_handles import source_registry
from foundation.structured_output import matches_schema
from test_responsibility import classification
from test_source_handles import wire_review
from test_structured_output import response

ROOT=Path(__file__).parents[1]
PROTOCOL=json.loads((ROOT/'protocols/observation-expressions-v12.json').read_text(encoding='utf-8'))
CASES=json.loads((ROOT/'fixtures/expression-contract-v1.json').read_text(encoding='utf-8'))['cases']
CONFIG=LLMConfig('LOCAL-FIXTURE-ONLY',base_url='https://api.deepseek.com/beta',max_calls=3)


def review_for(payload,mapping='PASS'):
    raw=wire_review(payload)
    for claim in raw['claims']:
        claim.pop('inspected_sources')
        claim.update(inspection_scope='COMPLETE_CONTEXT',attribution={'speaker':'system','stance':'endorsed'},boundary_status='PASS')
    raw['criteria'].append({'id':'attribution','status':'PASS','quotes':[],'rationale':'SCRIPTED fixture.'})
    next(c for c in raw['criteria'] if c['id']=='arithmetic_mapping')['status']=mapping
    return raw


class ExpressionTests(unittest.TestCase):
    artifact_directory=None

    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        path=Path(self.artifact_directory or directory.name);path.mkdir(parents=True,exist_ok=True)
        self.e=EvidenceRecorder(path/(self._testMethodName+'.jsonl'));self.addCleanup(self.e.close)
        self.worlds=[];self.adapters=[];self.addCleanup(self.capture)
        self.registry=source_registry([{'ref':{'space':'fact','identity':'work','revision':'1'},
            'content':{'task':'6kg cost 42; find cost of 15kg.', 'text':'42÷6=?'}}])

    def capture(self):
        for adapter in self.adapters:
            for record in adapter.records:self.e.emit('scripted_model_execution',**record)
        for index,h in enumerate(self.worlds):self.e.capture(h,'final:'+str(index))

    def case(self,name='unevaluated_known_operands'):
        return deepcopy(next(c for c in CASES if c['id']==name))

    def compute(self,case):
        result=check_expression_extraction(case['extraction'],case['candidate'],self.registry)
        self.e.emit('typed_calculation',case=case,result=result)
        return result

    def world(self,case):
        h,s,r,t,ctx,_,_=setup_boundary(prepare_candidate=False,protocol_payload=PROTOCOL,destination=CONFIG.base_url)
        self.worlds.append(h)
        return h,s,r,t,ctx,r.propose(ctx,'O','r1',case['candidate'])

    def adapter(self,case,mapping='PASS',raw=None):
        llm=DeepSeekAdapter(CONFIG,Mock(side_effect=[
            response(classification(payload=case['candidate']),'submit_responsibility'),
            response(case['extraction'],'submit_extraction'),
            response(raw or review_for(case['candidate'],mapping))]))
        self.adapters.append(llm)
        return llm

    def test_fixed_mappings_preserve_unknowns_and_numeric_stances(self):
        for case in CASES:
            with self.subTest(case=case['id']):
                result=self.compute(case)
                self.assertEqual(result['status'],case['expected_arithmetic_status'])
                self.assertEqual([c['computed'] for c in result['checks']],case['expected_computed'])
                self.assertTrue(result['mapping_required'])
        result=self.compute(self.case('reported_wrong_equality'))
        self.assertFalse(result['checks'][0]['relation_holds'])
        self.assertEqual(result['checks'][0]['status'],'PASS')

    def test_unevaluated_never_calculates_or_accepts_hidden_result(self):
        for mutation in ({'value':'7'},{'value':'?'},{'stance':'asserted_true'},{'left':'?'}):
            case=self.case();case['extraction']['segments'][0]['expressions'][0].update(mutation)
            with self.assertRaises(ContractError):self.compute(case)
        result=self.compute(self.case())
        self.assertIsNone(result['checks'][0]['computed'])
        self.assertEqual(result['checks'][0]['status'],'NOT_APPLICABLE')

    def test_full_span_and_field_bindings_do_not_repair_aliases(self):
        for mutation in ({'field':'candidate.description'},{'field':'content.description'},
                         {'text':'42÷6=?'},{'text':'invented quote'}):
            case=self.case();case['extraction']['segments'][0].update(mutation)
            with self.assertRaises(ContractError):self.compute(case)
        case=self.case();case['extraction']['segments'].append(deepcopy(case['extraction']['segments'][0]))
        with self.assertRaises(ContractError):self.compute(case)

    def test_expression_quote_positions_and_exact_sources_are_retained(self):
        case=self.case('mixed_unknown_and_correction');result=self.compute(case)
        for expression in result['checks']:
            self.assertEqual(case['candidate']['description'][expression['start']:expression['end']],expression['text'])
            self.assertEqual(expression['bound_sources'][0],self.registry[0 if expression['speaker']=='system' else 1])
        for sources in ([],['source_99'],['source_1','source_1'],[{'field':'text'}]):
            bad=self.case();bad['extraction']['segments'][0]['expressions'][0]['sources']=sources
            with self.assertRaises(ContractError):self.compute(bad)

    def test_repeated_expression_requires_unambiguous_quote_or_split(self):
        case=self.case();case['candidate']['description']='42÷6=?；42÷6=?'
        segment=case['extraction']['segments'][0];segment['text']=case['candidate']['description']
        segment['expressions'][0]['text']='42÷6=?'
        with self.assertRaisesRegex(ContractError,'Ambiguous'):self.compute(case)
        segment['expressions'][0]['text']='42÷6=?；'
        self.assertEqual(self.compute(case)['checks'][0]['start'],0)

    def test_unresolved_mapping_cannot_supply_guessed_numbers_or_skip_reason(self):
        for mutation in ({'value':'7'},{'operator':'divide'},{'reason':''}):
            case=self.case('asserted_unknown_relation');case['extraction']['segments'][0]['expressions'][0].update(mutation)
            with self.assertRaises(ContractError):self.compute(case)
        case=self.case();case['extraction']['segments'][0]['coverage']='UNRESOLVED'
        self.assertEqual(self.compute(case)['status'],'UNRESOLVED')

    def test_runtime_all_typed_variants_obey_review_and_commit(self):
        for case in CASES:
            with self.subTest(case=case['id']):
                h,s,r,t,ctx,candidate=self.world(case);llm=self.adapter(case)
                review=r.validate_with_llm(t,candidate,llm)
                self.assertEqual(review.status,case['expected_arithmetic_status'])
                outcome=r.commit(t,candidate,review.identity)
                self.assertEqual(outcome.status,'Committed' if review.status=='PASS' else 'ValidationFailed')
                self.assertEqual(llm.calls,3)
                extraction_input=json.loads(llm.records[1]['messages'][1]['content'])
                self.assertIn('source_registry',extraction_input)
                self.assertTrue(all(len(json.dumps(row['messages'],ensure_ascii=False))<=16000 for row in llm.records))

    def test_wrong_unevaluated_label_and_omitted_assertions_need_semantic_mapping(self):
        # Deliberately wrong type/omission: calculator cannot discover this by text heuristics.
        for omitted in (False,True):
            for mapping in ('FAIL','UNRESOLVED'):
                case=self.case('endorsed_wrong_equality')
                item=case['extraction']['segments'][0]['expressions'][0]
                item.update(type='UnevaluatedExpression',value=None,stance='not_asserted')
                if omitted:case['extraction']['segments'][0]['expressions']=[]
                self.assertEqual(self.compute(case)['status'],'PASS')
                h,s,r,t,ctx,candidate=self.world(case)
                review=r.validate_with_llm(t,candidate,self.adapter(case,mapping))
                self.assertEqual(review.status,'UNRESOLVED')
                self.assertEqual(r.commit(t,candidate,review.identity).status,'ValidationFailed')
                self.assertIsNone(h.get(candidate.record.ref))

    def test_missing_required_meaning_still_blocks_an_unevaluated_expression(self):
        case=self.case();h,s,r,t,ctx,candidate=self.world(case)
        raw=review_for(case['candidate'])
        next(c for c in raw['criteria'] if c['id']=='final_result').update(status='FAIL',quotes=[])
        review=r.validate_with_llm(t,candidate,self.adapter(case,raw=raw))
        self.assertEqual(review.status,'FAIL')
        self.assertEqual(r.commit(t,candidate,review.identity).status,'ValidationFailed')

    def test_missing_mapping_review_or_wrong_field_stops_without_retry(self):
        for label in ('mapping','field'):
            case=self.case();h,s,r,t,ctx,candidate=self.world(case);raw=review_for(case['candidate'])
            if label=='mapping':raw['criteria']=[c for c in raw['criteria'] if c['id']!='arithmetic_mapping']
            else:raw['claims'][0]['field']='candidate.description'
            llm=self.adapter(case,raw=raw)
            with self.assertRaises((ContractError,ModelFailure)):r.validate_with_llm(t,candidate,llm)
            with self.assertRaisesRegex(ContractError,'AlreadyAttempted'):r.validate_with_llm(t,candidate,llm)
            self.assertEqual(llm.calls,3);self.assertIsNone(h.get(candidate.record.ref))

    def test_extraction_wrong_field_fails_before_semantic_review(self):
        case=self.case();case['extraction']['segments'][0]['field']='candidate.description'
        h,s,r,t,ctx,candidate=self.world(case);llm=self.adapter(case)
        with self.assertRaises(ModelFailure):r.validate_with_llm(t,candidate,llm)
        self.assertEqual(llm.calls,2)
        self.assertTrue(any(rec.kind=='ArithmeticExtractionFailed' for rec in h.executions.records()))

    def test_commit_recomputes_exact_result_and_rejects_cross_candidate_reuse(self):
        case=self.case();h,s,r,t,ctx,candidate=self.world(case)
        review=r.validate_with_llm(t,candidate,self.adapter(case))
        ref=r._arithmetic_executions[candidate.identity]
        other=r.propose(ctx,'O','r2',{'description':'Different candidate'})
        with self.assertRaisesRegex(ContractError,'BindingMismatch'):r._checked_arithmetic(other,ref)
        saved=h.get(ref).payload;saved['result']['checks'][0]['computed']='7'
        forged=r.execution('ArithmeticExtractionExecution',ctx.subject,saved)
        with self.assertRaisesRegex(ContractError,'ComputationMismatch'):r._checked_arithmetic(candidate,forged)
        validation=h.get(review.execution).payload;validation['arithmetic_execution']=json_value(forged)
        forged_validation=r.execution('SemanticValidationExecution',ctx.subject,validation)
        r._reviews[review.identity]=replace(review,execution=forged_validation)
        self.assertEqual(r.commit(t,candidate,review.identity).status,'ValidationFailed')

    def test_old_extraction_format_remains_strict_and_new_profile_is_opt_in(self):
        case=self.case()
        with self.assertRaises(ContractError):check_arithmetic_extraction(case['extraction'],case['candidate'])
        old=json.loads((ROOT/'protocols/observation-smoke-v11.json').read_text(encoding='utf-8'))
        self.assertNotIn('arithmetic_extraction_format',old)
        for key in ('generation_system','responsibility_admission','validation_format'):
            self.assertEqual(PROTOCOL[key],old[key])
        self.assertEqual([c['id'] for c in PROTOCOL['criteria']],[c['id'] for c in old['criteria']])
        self.assertEqual([c for c in PROTOCOL['criteria'] if c['id']!='arithmetic_mapping'],
                         [c for c in old['criteria'] if c['id']!='arithmetic_mapping'])

    def test_schema_and_registration_enforce_exact_fields_and_required_mapping(self):
        self.assertEqual(check_observation_contract(PROTOCOL)['status'],'PASS')
        for label in ('field','mapping','format','expression_type'):
            bad=deepcopy(PROTOCOL)
            if label=='field':bad['output_contracts']['responsibility']['parameters']['properties']['segments']['items']['properties']['field'].pop('enum')
            elif label=='mapping':
                bad['criteria']=[c for c in bad['criteria'] if c['id']!='arithmetic_mapping']
                bad['output_contracts']['validation']['parameters']['properties']['criteria']['items']['properties']['id']['enum'].remove('arithmetic_mapping')
            elif label=='format':bad['arithmetic_extraction_format']='invented-version'
            else:bad['output_contracts']['extraction']['parameters']['properties']['segments']['items']['properties']['expressions']['items']['properties']['type']['enum'].append('Skip')
            with self.assertRaises(ContractError):setup_boundary(prepare_candidate=False,protocol_payload=bad,destination=CONFIG.base_url)
        case=self.case();case['extraction']['segments'][0]['field']='candidate.description'
        self.assertFalse(matches_schema(case['extraction'],PROTOCOL['output_contracts']['extraction']['parameters']))


if __name__=='__main__':unittest.main()
