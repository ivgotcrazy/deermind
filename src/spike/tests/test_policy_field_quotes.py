"""Scalar handles and exact unique quote binding; scripted semantics only."""
import copy,json,tempfile,unittest
from dataclasses import replace
from pathlib import Path
from foundation.boundary import digest
from foundation.cases import EvidenceRecorder
from foundation.policy_cases import PolicyWorld
from foundation.policy_field_quotes import contract,registry,expand
from foundation.runtime import ContractError
from foundation.llm import ModelFailure
from foundation.records import json_value
from run_policy_validation import load_design
import test_policy_disposition as base

class FieldQuoteTests(unittest.TestCase):
    artifact_directory=None
    payload=base.DispositionTests.payload
    adapter=base.DispositionTests.adapter
    review=base.DispositionTests.review
    set_status=base.DispositionTests.set_status
    gap=base.DispositionTests.gap
    capture=base.DispositionTests.capture
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        folder=self.artifact_directory or Path(tmp.name);folder.mkdir(parents=True,exist_ok=True)
        self.e=EvidenceRecorder(folder/(self._testMethodName+'.jsonl'));self.addCleanup(self.e.close)
        self.fixture,_=load_design();self.definition=json.loads((Path(__file__).resolve().parents[1]/'protocols/policy-e1-v4.json').read_text(encoding='utf-8'))
        self.w=PolicyWorld(self.e,self.definition,self.fixture,self.fixture['variants'][1],rule_revision='v4')
        self.adapters=[];self.addCleanup(self.capture)
        self.p=self.payload();self.p['rationale']='提示帮助定位，重新计算仍由学习者完成。'
        self.c=self.w.runtime.propose(self.w.context,'P','r1',self.p)
    def output(self,b):
        o=base.DispositionTests.output(self,b);entries=b['quote_registry']
        for f in o['findings']:
            f['candidate_quotes']=[{'handle':next(r['handle'] for r in entries['candidate'] if r['field']==q['field']),'quote':q['quote']} for q in f['candidate_quotes']]
            f['source_quotes']=[{'handle':next(r['handle'] for r in entries['source'] if (r['ref'],r['field'])==(q['ref'],q['field'])),'quote':q['quote']} for q in f['source_quotes']]
        return o
    def test_generation_review_commit_and_dynamic_enums(self):
        a=self.adapter();c=self.w.runtime.generate_with_llm(self.w.tokens['interaction'],self.w.context,a,identity='P')
        r=self.w.runtime.validate_with_llm(self.w.tokens['interaction'],c,a)
        self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],c,r.identity).status,'Committed')
        self.assertEqual(self.w.runtime.validate_with_llm(self.w.tokens['interaction'],c,a),r);self.assertEqual(len(a.records),2)
        wire=a.records[1];b=json.loads(wire['messages'][1]['content']);self.assertEqual(b['candidate_digest'],digest(c))
        q=wire['output_contract']['parameters']['properties']['findings']['items']['properties']['source_quotes']['items']['properties']
        self.assertEqual(set(q),{'handle','quote'});self.assertEqual(q['handle']['enum'],[r['handle'] for r in b['quote_registry']['source']])
        self.assertNotIn('allowed_action_refs',[r['field'] for r in b['quote_registry']['source']])
        self.assertTrue(all('text' not in row for rows in b['quote_registry'].values() for row in rows))
        self.assertLessEqual(len(json.dumps(wire['messages'],ensure_ascii=False)),16000)
    def test_registry_omits_arrays_objects_numbers_and_hidden_fields(self):
        refs={'space':'fact','identity':'r','revision':'1'};e=registry({'text':'甲乙','items':[],'value':3},[{'ref':refs,'content':{'text':'甲乙','array':['甲乙'],'object':{},'number':1}}])
        self.assertEqual([r['field'] for r in e['candidate']],['text']);self.assertEqual([r['field'] for r in e['source']],['text'])
    def test_exact_unicode_quote_expands_to_codepoint_offsets(self):
        e=registry({'rationale':'前缀🙂商仍独立算'},[]);o={'findings':[{'candidate_quotes':[{'handle':e['candidate'][0]['handle'],'quote':'🙂商仍独立算'}],'source_quotes':[]}]}
        q=expand(o,e)['findings'][0]['candidate_quotes'][0];self.assertEqual((q['start'],q['end']),('2','8'))
    def test_overlapping_repeated_quote_is_rejected(self):
        e=registry({'rationale':'aaa'},[]);o={'findings':[{'candidate_quotes':[{'handle':e['candidate'][0]['handle'],'quote':'aa'}],'source_quotes':[]}]}
        with self.assertRaisesRegex(ContractError,'DispositionFieldQuoteAmbiguous'):expand(o,e)
    def test_complete_longer_quote_disambiguates(self):
        e=registry({'rationale':'相同。相同但有条件。'},[]);o={'findings':[{'candidate_quotes':[{'handle':e['candidate'][0]['handle'],'quote':'相同但有条件。'}],'source_quotes':[]}]}
        self.assertEqual(expand(o,e)['findings'][0]['candidate_quotes'][0]['start'],'3')
    def test_unknown_handle_and_empty_quote_rejected(self):
        e=registry({'rationale':'甲'},[])
        for handle,part,reason in [('unknown','甲','DispositionUnknownFieldHandle'),(e['candidate'][0]['handle'],'','DispositionEmptyFieldQuote')]:
            with self.assertRaisesRegex(ContractError,reason):expand({'findings':[{'candidate_quotes':[{'handle':handle,'quote':part}],'source_quotes':[]}]},e)
    def test_normalization_and_paraphrase_not_accepted(self):
        def edit(o,b):o['findings'][0]['candidate_quotes'][0]['quote']='提示帮助 定位'
        with self.assertRaisesRegex(ContractError,'DispositionFieldQuoteNotFound'):self.review(edit)
    def test_unknown_source_handle_cannot_register_review(self):
        def edit(o,b):o['findings'][0]['source_quotes'][0]['handle']='audit-field'
        with self.assertRaisesRegex(ModelFailure,'OutputSchemaMismatch'):self.review(edit)
        self.assertEqual(self.w.runtime.validation_history(self.c),())
    def test_conflict_cannot_be_hidden_by_top_level_pass(self):
        def edit(o,b):self.set_status(o,'FAIL');o['status']='PASS'
        with self.assertRaisesRegex(ContractError,'DispositionOverallContradiction'):self.review(edit)
    def test_withheld_registry_and_valid_unresolved_no_commit(self):
        self.w.runtime.withhold_policy_review_material(self.w.context,(self.w.work,));r=self.review(self.gap)
        self.assertEqual(r.status,'UNRESOLVED');self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],self.c,r.identity).status,'ValidationFailed')
        body=json.loads(self.adapters[0].records[0]['messages'][1]['content'])
        self.assertNotIn(json_value(self.w.work),[q['ref'] for q in body['quote_registry']['source']])
    def test_commit_recomputes_handle_binding(self):
        r=self.review();details=json.loads(r.details_json);details['findings'][0]['source_quotes'][0]['handle']='unknown'
        self.w.runtime._reviews[r.identity]=replace(r,details_json=json.dumps(details))
        self.assertIn('DispositionValidationEvidenceInvalid',self.w.runtime.validate(self.c,r.identity))
    def test_false_semantic_pass_still_possible(self):
        self.p['rationale']='完全没有替代定位工作。';self.c=self.w.runtime.propose(self.w.context,'P','r2',self.p)
        r=self.review();self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],self.c,r.identity).status,'Committed')
