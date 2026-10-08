"""Scripted findings exercise mechanical gates; they are not semantic evidence."""
import copy,json,tempfile,unittest
from dataclasses import replace
from pathlib import Path
from foundation.boundary import digest
from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter,LLMConfig
from foundation.policy_cases import PolicyWorld
from foundation.policy_disposition import RULES,check
from foundation.records import json_value
from foundation.runtime import ContractError
from run_policy_validation import load_design
import test_policy

class DispositionTests(unittest.TestCase):
    artifact_directory=None
    payload=test_policy.PolicyTests.payload
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        folder=self.artifact_directory or Path(tmp.name);folder.mkdir(parents=True,exist_ok=True)
        self.e=EvidenceRecorder(folder/(self._testMethodName+'.jsonl'));self.addCleanup(self.e.close)
        self.fixture,_=load_design();self.definition=json.loads((Path(__file__).resolve().parents[1]/'protocols/policy-e1-v3.json').read_text(encoding='utf-8'))
        self.w=PolicyWorld(self.e,self.definition,self.fixture,self.fixture['variants'][1],rule_revision='v3')
        self.adapters=[];self.addCleanup(self.capture)
        self.p=self.payload();self.p['rationale']='提示帮助定位，重新计算仍由学习者完成。'
        self.c=self.w.runtime.propose(self.w.context,'P','r1',self.p)
    def capture(self):
        for a in self.adapters:
            for r in a.records:self.e.emit('scripted_execution',**r)
        self.e.capture(self.w.h,'final')
    def output(self,b):
        text=b['candidate']['rationale'];source=next(r for r in b['context'] if r['kind']=='CurrentInteractionInput');st=source['content']['text']
        f={'id':'f1','rules':list(RULES),'relation':'SUPPORTED','candidate_quotes':[{'field':'rationale','start':'0','end':str(len(text)),'quote':text}],
            'source_quotes':[{'ref':source['ref'],'field':'text','start':'0','end':str(len(st)),'quote':st}],'gap_ids':[],'rationale':'Injected fixture, not semantic evidence.'}
        return {k:b[k] for k in ('candidate_digest','context_id','rule_ref','material_record_ref')} | {'reviewed_fields':list(b['candidate']),'findings':[f],'review_material_gaps':[],
            'checks':[{'id':r,'status':'PASS','reason_code':'SATISFIED','finding_ids':['f1'],'rationale':'Scripted.'} for r in RULES],'status':'PASS','rationale':'Scripted.'}
    def adapter(self,edit=lambda o,b:None):
        def transport(url,key,wire,timeout):
            name=wire['tools'][0]['function']['name'];b=json.loads(wire['messages'][1]['content'])
            if name=='submit_policy':v=self.p
            else:v=self.output(b);edit(v,b)
            return {'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[{'id':'fixture','type':'function','function':{'name':name,'arguments':json.dumps(v)}}]}}]}
        a=DeepSeekAdapter(LLMConfig('LOCAL',base_url=self.definition['provider_endpoint'],max_calls=2),transport);self.adapters.append(a);return a
    def review(self,edit=lambda o,b:None):return self.w.runtime.validate_with_llm(self.w.tokens['interaction'],self.c,self.adapter(edit))
    def set_status(self,o,state):
        o['findings'][0]['relation']={'FAIL':'CONTRADICTED','UNRESOLVED':'UNDETERMINED'}[state]
        for row in o['checks']:row.update(status=state,reason_code='CONTENT_DEFECT' if state=='FAIL' else 'INSUFFICIENT_REVIEW')
        o['status']=state
    def gap(self,o,b):
        self.set_status(o,'UNRESOLVED');m=next(m for m in b['materials'] if m['state']=='WITHHELD_FOR_REVIEW')
        o['review_material_gaps']=[{'id':'g1','rules':list(RULES),'material_id':m['id'],'rationale':'Trusted withheld material.'}]
        o['findings'][0]['gap_ids']=['g1'];o['findings'][0]['source_quotes']=[]
    def test_generation_once_review_and_positive_commit(self):
        a=self.adapter();c=self.w.runtime.generate_with_llm(self.w.tokens['interaction'],self.w.context,a,identity='P')
        r=self.w.runtime.validate_with_llm(self.w.tokens['interaction'],c,a)
        self.assertEqual(self.w.runtime.validate_with_llm(self.w.tokens['interaction'],c,a),r);self.assertEqual(len(a.records),2)
        self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],c,r.identity).status,'Committed')
        self.assertEqual(json.loads(a.records[1]['messages'][1]['content'])['candidate_digest'],digest(c))
    def test_conflict_with_check_pass_rejected_and_no_retry(self):
        def edit(o,b):o['findings'][0]['relation']='CONTRADICTED'
        with self.assertRaisesRegex(ContractError,'DispositionCheckContradiction'):self.review(edit)
        self.assertEqual(self.w.runtime.validation_history(self.c),())
        with self.assertRaisesRegex(ContractError,'CandidateValidationAlreadyAttempted'):self.review()
    def test_conflict_with_overall_pass_rejected(self):
        def edit(o,b):self.set_status(o,'FAIL');o['status']='PASS'
        with self.assertRaisesRegex(ContractError,'DispositionOverallContradiction'):self.review(edit)
    def test_valid_fail_blocks_commit(self):
        r=self.review(lambda o,b:self.set_status(o,'FAIL'));self.assertEqual(r.status,'FAIL')
        self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],self.c,r.identity).status,'ValidationFailed')
    def test_trusted_withheld_unresolved_blocks_commit_and_freezes_view(self):
        self.w.runtime.withhold_policy_review_material(self.w.context,(self.w.work,));r=self.review(self.gap)
        self.assertEqual(r.status,'UNRESOLVED');self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],self.c,r.identity).status,'ValidationFailed')
        wire=json.loads(self.adapters[-1].records[0]['messages'][1]['content'])
        self.assertNotIn(json_value(self.w.work),[r['ref'] for r in wire['context']]);self.assertIn(self.w.work,[i.record.ref for i in self.w.context.items])
        with self.assertRaisesRegex(ContractError,'ReviewMaterialViewFrozen'):self.w.runtime.withhold_policy_review_material(self.w.context,())
    def test_declared_gap_cannot_pass(self):
        self.w.runtime.withhold_policy_review_material(self.w.context,(self.w.work,))
        def edit(o,b):self.gap(o,b);o['checks'][0].update(status='PASS',reason_code='SATISFIED')
        with self.assertRaisesRegex(ContractError,'DispositionCheckContradiction'):self.review(edit)
    def test_missing_material_does_not_cancel_known_conflict(self):
        self.w.runtime.withhold_policy_review_material(self.w.context,(self.w.work,))
        def edit(o,b):
            self.gap(o,b);f=copy.deepcopy(o['findings'][0]);f.update(id='f2',rules=['S3'],relation='CONTRADICTED',gap_ids=[])
            o['findings'].append(f);o['checks'][2].update(status='FAIL',reason_code='CONTENT_DEFECT',finding_ids=['f1','f2']);o['status']='FAIL'
        self.assertEqual(self.review(edit).status,'FAIL')
    def test_candidate_cannot_invent_unavailability(self):
        def edit(o,b):
            self.set_status(o,'UNRESOLVED');o['review_material_gaps']=[{'id':'g1','rules':list(RULES),'material_id':b['materials'][0]['id'],'rationale':'Invented missing material.'}];o['findings'][0]['gap_ids']=['g1']
        with self.assertRaisesRegex(ContractError,'DispositionUntrustedMaterialGap'):self.review(edit)
    def test_source_quote_outside_visible_view_rejected(self):
        self.w.runtime.withhold_policy_review_material(self.w.context,(self.w.work,))
        def edit(o,b):o['findings'][0]['source_quotes'][0]['ref']=json_value(self.w.work)
        with self.assertRaisesRegex(ContractError,'DispositionSourceOutsideContext'):self.review(edit)
    def test_quote_outside_projected_fields_rejected(self):
        def edit(o,b):o['findings'][0]['source_quotes'][0]['field']='audit_only'
        with self.assertRaisesRegex(ContractError,'DispositionSourceOutsideContext'):self.review(edit)
    def test_exact_candidate_binding_and_unicode_quote(self):
        with self.assertRaisesRegex(ContractError,'DispositionBindingMismatch'):self.review(lambda o,b:o.update(candidate_digest='wrong'))
        self.c=self.w.runtime.propose(self.w.context,'P-more','r1',self.p)
        def edit(o,b):o['findings'][0]['candidate_quotes'][0]['end']='1'
        with self.assertRaisesRegex(ContractError,'DispositionQuoteMismatch'):self.review(edit)
    def test_coverage_and_duplicate_obligation_rejected(self):
        with self.assertRaisesRegex(ContractError,'DispositionFieldCoverage'):self.review(lambda o,b:o['reviewed_fields'].pop())
        self.c=self.w.runtime.propose(self.w.context,'P-more','r1',self.p)
        with self.assertRaisesRegex(ContractError,'DispositionRuleCoverage'):self.review(lambda o,b:o['checks'].append(copy.deepcopy(o['checks'][0])))
    def test_commit_rechecks_details(self):
        r=self.review();details=json.loads(r.details_json);details['findings'][0]['relation']='CONTRADICTED'
        self.w.runtime._reviews[r.identity]=replace(r,details_json=json.dumps(details))
        self.assertIn('DispositionValidationEvidenceInvalid',self.w.runtime.validate(self.c,r.identity))
    def test_semantic_false_pass_remains_possible(self):
        self.p['rationale']='没有替代任何定位工作。';self.c=self.w.runtime.propose(self.w.context,'P','r2',self.p)
        r=self.review();self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],self.c,r.identity).status,'Committed')
