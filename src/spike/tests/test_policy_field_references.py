"""Versioned host-resolved field evidence; all judgments are scripted fixtures."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from foundation.boundary import digest
from foundation.cases import EvidenceRecorder
from foundation.llm import ModelFailure
from foundation.policy_cases import PolicyWorld
from foundation.policy_field_references import registry, expand
from foundation.records import json_value
from foundation.runtime import ContractError
from run_policy_validation import load_design
import test_policy_disposition as base


class FieldReferenceTests(unittest.TestCase):
    artifact_directory = None
    payload = base.DispositionTests.payload
    adapter = base.DispositionTests.adapter
    review = base.DispositionTests.review
    set_status = base.DispositionTests.set_status
    gap = base.DispositionTests.gap
    capture = base.DispositionTests.capture

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = self.artifact_directory or Path(temporary.name)
        folder.mkdir(parents=True, exist_ok=True)
        self.e = EvidenceRecorder(folder/(self._testMethodName+'.jsonl'))
        self.addCleanup(self.e.close)
        self.fixture,_ = load_design()
        self.definition = json.loads((Path(__file__).resolve().parents[1]/'protocols/policy-e1-v5.json').read_text(encoding='utf-8'))
        self.w = PolicyWorld(self.e,self.definition,self.fixture,self.fixture['variants'][1],rule_revision='v5')
        self.adapters = []
        self.addCleanup(self.capture)
        self.p = self.payload()
        self.p['rationale'] = '提示帮助定位，重新计算仍由学习者完成。'
        self.c = self.w.runtime.propose(self.w.context,'P','r1',self.p)

    def output(self, body):
        output = base.DispositionTests.output(self,body)
        entries = body['quote_registry']
        for finding in output['findings']:
            finding['candidate_quotes'] = [{'handle':next(row['handle'] for row in entries['candidate']
                if row['field']==quote['field'])} for quote in finding['candidate_quotes']]
            finding['source_quotes'] = [{'handle':next(row['handle'] for row in entries['source']
                if (row['ref'],row['field'])==(quote['ref'],quote['field']))} for quote in finding['source_quotes']]
        return output

    def test_generation_review_commit_with_nonempty_dynamic_handle_schema(self):
        adapter = self.adapter()
        candidate = self.w.runtime.generate_with_llm(self.w.tokens['interaction'],self.w.context,adapter,identity='P')
        review = self.w.runtime.validate_with_llm(self.w.tokens['interaction'],candidate,adapter)
        self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],candidate,review.identity).status,'Committed')
        self.assertEqual(self.w.runtime.validate_with_llm(self.w.tokens['interaction'],candidate,adapter),review)
        self.assertEqual(adapter.calls,2)
        wire = adapter.records[1]
        body = json.loads(wire['messages'][1]['content'])
        self.assertEqual(body['candidate_digest'],digest(candidate))
        fields = [r['field'] for r in body['quote_registry']['candidate']]
        self.assertNotIn('defer_condition',fields)
        self.assertIn('defer_condition',json.loads(review.details_json)['reviewed_fields'])
        self.assertTrue(all('text' not in r for rows in body['quote_registry'].values() for r in rows))
        for side in ('candidate','source'):
            schema = wire['output_contract']['parameters']['properties']['findings']['items']['properties'][side+'_quotes']['items']
            self.assertEqual(set(schema['properties']),{'handle'})
            self.assertEqual(schema['properties']['handle']['enum'],[r['handle'] for r in body['quote_registry'][side]])
        self.assertLessEqual(len(json.dumps(wire['messages'],ensure_ascii=False)),16000)

    def test_registry_excludes_empty_and_nonstring_fields_on_both_sides(self):
        ref = {'space':'fact','identity':'source','revision':'1'}
        entries = registry({'empty':'','text':'甲','array':[],'number':1},
            [{'ref':ref,'content':{'empty':'','text':'乙','object':{},'null':None}}])
        self.assertEqual([r['field'] for r in entries['candidate']],['text'])
        self.assertEqual([r['field'] for r in entries['source']],['text'])
        self.assertEqual(registry({'empty':''},[{'ref':ref,'content':{'empty':''}}]),{'candidate':[],'source':[]})

    def test_full_unicode_and_repeated_text_resolved_without_model_quote_or_offsets(self):
        text = '前缀🙂相同。相同。'
        entries = registry({'rationale':text},[])
        output = {'findings':[{'candidate_quotes':[{'handle':entries['candidate'][0]['handle']}],'source_quotes':[]}]}
        quote = expand(output,entries)['findings'][0]['candidate_quotes'][0]
        self.assertEqual(quote,{'field':'rationale','start':'0','end':str(len(text)),'quote':text})
        self.assertEqual(output['findings'][0]['candidate_quotes'][0],{'handle':entries['candidate'][0]['handle']})

    def test_no_intervention_keeps_empty_action_fields_reviewed(self):
        self.p = self.payload('NoIntervention')
        self.c = self.w.runtime.propose(self.w.context,'P','r2',self.p)
        review = self.review()
        self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],self.c,review.identity).status,'Committed')
        body = json.loads(self.adapters[-1].records[0]['messages'][1]['content'])
        self.assertNotIn('action_identity',[r['field'] for r in body['quote_registry']['candidate']])
        self.assertEqual(set(json.loads(review.details_json)['reviewed_fields']),set(self.p))

    def test_defer_still_requires_a_concrete_condition(self):
        self.p = self.payload('Defer')
        self.c = self.w.runtime.propose(self.w.context,'P','r2',self.p)
        review = self.review()
        self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],self.c,review.identity).status,'Committed')
        self.p['defer_condition'] = ''
        self.c = self.w.runtime.propose(self.w.context,'P','r3',self.p)
        review = self.review()
        self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],self.c,review.identity).reason,'DeferConditionShapeInvalid')

    def test_omitting_empty_field_from_review_coverage_is_rejected(self):
        with self.assertRaisesRegex(ContractError,'DispositionFieldCoverage'):
            self.review(lambda o,b:o['reviewed_fields'].remove('defer_condition'))
        self.assertEqual(self.w.runtime.validation_history(self.c),())

    def test_empty_field_handle_rejected_without_retry(self):
        empty_handle = 'candidate_'+str(sorted(self.p).index('defer_condition'))
        def edit(output,body):
            output['findings'][0]['candidate_quotes'].append({'handle':empty_handle})
        with self.assertRaisesRegex(ModelFailure,'OutputSchemaMismatch'):
            self.review(edit)
        self.assertEqual(self.adapters[-1].calls,1)
        self.assertEqual(self.w.runtime.validation_history(self.c),())
        with self.assertRaisesRegex(ContractError,'CandidateValidationAlreadyAttempted'):
            self.review()
        self.assertEqual(self.adapters[-1].calls,0)

    def test_model_supplied_quote_is_rejected_by_wire_schema(self):
        def edit(output,body):
            output['findings'][0]['candidate_quotes'][0]['quote'] = body['candidate']['rationale']
        with self.assertRaisesRegex(ModelFailure,'OutputSchemaMismatch'):
            self.review(edit)

    def test_wrong_context_binding_cannot_register_review(self):
        with self.assertRaisesRegex(ContractError,'DispositionBindingMismatch'):
            self.review(lambda o,b:o.update(context_id='another-context'))
        self.assertEqual(self.w.runtime.validation_history(self.c),())

    def test_withheld_sources_cannot_be_selected_and_unresolved_cannot_commit(self):
        self.w.runtime.withhold_policy_review_material(self.w.context,(self.w.work,))
        review = self.review(self.gap)
        self.assertEqual(review.status,'UNRESOLVED')
        self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],self.c,review.identity).status,'ValidationFailed')
        body = json.loads(self.adapters[-1].records[0]['messages'][1]['content'])
        self.assertNotIn(json_value(self.w.work),[r['ref'] for r in body['quote_registry']['source']])
        with self.assertRaisesRegex(ContractError,'ReviewMaterialViewFrozen'):
            self.w.runtime.withhold_policy_review_material(self.w.context,())

    def test_unknown_source_handle_cannot_register_review(self):
        def edit(output,body):
            output['findings'][0]['source_quotes'][0]['handle']='unregistered-source'
        with self.assertRaisesRegex(ModelFailure,'OutputSchemaMismatch'):
            self.review(edit)
        self.assertEqual(self.w.runtime.validation_history(self.c),())

    def test_known_conflict_cannot_be_overridden_by_overall_pass(self):
        def edit(output,body):
            self.set_status(output,'FAIL')
            output['status']='PASS'
        with self.assertRaisesRegex(ContractError,'DispositionOverallContradiction'):
            self.review(edit)
        self.c = self.w.runtime.propose(self.w.context,'P','r2',self.p)
        review = self.review(lambda o,b:self.set_status(o,'FAIL'))
        self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],self.c,review.identity).status,'ValidationFailed')

    def test_commit_rechecks_host_reference_and_exact_review_details(self):
        review = self.review()
        details = json.loads(review.details_json)
        details['findings'][0]['source_quotes'][0]['handle']='unregistered-source'
        self.w.runtime._reviews[review.identity] = replace(review,details_json=json.dumps(details))
        self.assertIn('DispositionValidationEvidenceInvalid',self.w.runtime.validate(self.c,review.identity))

    def test_wrong_semantic_pass_remains_possible_with_valid_references(self):
        self.p['rationale']='完全没有替代任何定位工作。'
        self.c = self.w.runtime.propose(self.w.context,'P','r2',self.p)
        review = self.review()
        self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],self.c,review.identity).status,'Committed')

    def test_revision_mismatch_and_old_wire_contract_are_rejected(self):
        with self.assertRaisesRegex(ContractError,'PolicyRuleRevisionMismatch'):
            PolicyWorld(self.e,self.definition,self.fixture,self.fixture['variants'][1],rule_revision='v4')
        bad = copy.deepcopy(self.definition)
        old = json.loads((Path(__file__).resolve().parents[1]/'protocols/policy-e1-v4.json').read_text(encoding='utf-8'))
        bad['output_contracts']['validation']=old['output_contracts']['validation']
        with self.assertRaisesRegex(ContractError,'DispositionProtocolMismatch'):
            PolicyWorld(self.e,bad,self.fixture,self.fixture['variants'][1],rule_revision='v5')
