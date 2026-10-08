"""Scripted integration, actual request binding and finite termination only."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter, LLMConfig, ModelFailure
from foundation.working_campaign import CallBudget, WorkingWorld, run_batch
from preflight_restricted_working import CONFIG, preflight


HOST_KEYS = {'required_content','expected_semantic','expected_utility','required_detection',
             'source_case','execution_order','stop_rules','budget','limitations'}


def audit_messages(messages):
    def walk(value):
        if isinstance(value,dict):
            if HOST_KEYS.intersection(value): raise AssertionError('Host label key in outgoing request')
            for item in value.values(): walk(item)
        elif isinstance(value,list):
            for item in value: walk(item)
    for message in messages:
        if 'RUNTIME_HOST_ONLY_SENTINEL' in message['content']:
            raise AssertionError('Host label sentinel in outgoing request')
        if message['role']=='user': walk(json.loads(message['content']))


class ScriptedTransport:
    """Explicit host-side fixtures. No general semantic interpretation."""
    def __init__(self):
        self.spec = None
        self.wires = []
        self.force_first_pass = False
        self.fail_call = None
        self.normal_outcome = 'Execute'

    def before_case(self,spec): self.spec = spec

    def __call__(self,url,key,wire,timeout):
        audit_messages(wire['messages'])
        self.wires.append({'messages':wire['messages'],'contract':wire['tools'][0]['function'], 'timeout':timeout})
        if self.fail_call == len(self.wires): raise TimeoutError('Injected offline failure')
        contract = wire['tools'][0]['function']; name = contract['name']
        body = json.loads(wire['messages'][1]['content'])
        negative = self.spec.get('expected_semantic') == 'FAIL' and not self.force_first_pass
        if name == 'submit_observation': value = {'description':'本地脚本观察，仅用于测试绑定和执行顺序。'}
        elif name == 'submit_responsibility':
            value = {'segments':[{'field':'description','text':body['candidate']['description'],
                'role':'ability_inference' if negative else 'local_observation','rationale':'Explicit scripted fixture.'}]}
        elif name == 'submit_extraction':
            key = 'expressions' if 'expressions' in contract['parameters']['properties']['segments']['items']['properties'] else 'assertions'
            value = {'segments':[{'field':'description','text':body['candidate']['description'],'coverage':'COMPLETE',key:[]}]}
        elif name == 'submit_policy':
            source = next(i for i in body if i['kind']=='CurrentInteractionInput')
            value = {'outcome':'Execute','action_identity':'HintCheckStep','action_revision':'e1-v1',
                'exact_payload':'再检查一下 42÷6。','executor_target':'mock-display','episode':'working-apple-episode',
                'rationale':'SCRIPTED local hint for integration only.','context_refs':[source['ref']],
                'expected_disclosure':'SCRIPTED expected cue.','uncertainty':'SCRIPTED no quality claim.','defer_condition':''}
            if self.normal_outcome != 'Execute':
                value.update(outcome=self.normal_outcome,action_identity='',action_revision='',exact_payload='',executor_target='')
        elif name == 'submit_policy_utility':
            status = self.spec.get('expected_utility','PASS')
            value = {'scores':[{'id':r,'status':status,'reason':'Scripted measurement.'} for r in body['rubric']]}
        elif 'checks' in contract['parameters']['properties']:
            status = 'FAIL' if negative else 'PASS'
            registry = body['quote_registry']
            cq = next(r for r in registry['candidate'] if r['field']=='rationale')
            sq = next(r for r in registry['source'] if r['field']=='text')
            source = next(i for i in body['context'] if i['ref']==sq['ref'])
            rules = ['S1','S2','S3','S4','S5']
            finding = {'id':'f1','rules':rules,'relation':'CONTRADICTED' if negative else 'SUPPORTED',
                'candidate_quotes':[{'handle':cq['handle'],'quote':body['candidate']['rationale']}],
                'source_quotes':[{'handle':sq['handle'],'quote':source['content']['text']}],
                'gap_ids':[],'rationale':'Explicit scripted relationship, not semantic evidence.'}
            value = {k:body[k] for k in ('candidate_digest','context_id','rule_ref','material_record_ref')}
            value.update(reviewed_fields=list(body['candidate']),findings=[finding],review_material_gaps=[],
                checks=[{'id':r,'status':status,'reason_code':'CONTENT_DEFECT' if negative else 'SATISFIED',
                         'finding_ids':['f1'],'rationale':'Scripted.'} for r in rules],status=status,rationale='Scripted.')
        else:
            payload = body['candidate']; text = payload['description']
            ids = contract['parameters']['properties']['criteria']['items']['properties']['id']['enum']
            sources = contract['parameters']['properties']['claims']['items']['properties']['sources']['items']['enum']
            value = {'reviewed_fields':['description'],
                'criteria':[{'id':r,'status':'FAIL' if negative and r=='boundary' else 'PASS',
                    'quotes':[{'field':'description','text':text}],'rationale':'Explicit scripted judgment.'} for r in ids],
                'claims':[{'field':'description','text':text,'kind':'paraphrase','reported_quote':None,'status':'PASS',
                    'sources':[sources[0]],'rationale':'Scripted support.','support':'supported',
                    'attribution':{'speaker':'system','stance':'endorsed'},'boundary_status':'FAIL' if negative else 'PASS',
                    'inspection_scope':'COMPLETE_CONTEXT'}]}
        return {'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[
            {'id':'local','type':'function','function':{'name':name,'arguments':json.dumps(value,ensure_ascii=False)}}]}}]}


class WorkingCampaignTests(unittest.TestCase):
    def setUp(self):
        preflight()
        self.config = json.loads(CONFIG.read_text(encoding='utf-8'))
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.transport = ScriptedTransport()
        self.adapter = DeepSeekAdapter(LLMConfig('OFFLINE-ONLY',base_url='https://api.deepseek.com/beta',
            max_calls=58,max_output_tokens=4096),self.transport)

    def run_batch(self,**kwargs):
        return run_batch(self.config,self.adapter,lambda id:EvidenceRecorder(self.directory/(id+'.jsonl')),
                         before_case=self.transport.before_case,**kwargs)

    def test_all_pinned_cases_use_real_shared_bindings_and_no_host_labels(self):
        result = self.run_batch()
        self.assertIsNone(result['stop_reason'])
        self.assertEqual([r['execution'] for r in result['rows']],['COMPLETED']*10)
        self.assertEqual(result['calls'],51)
        self.assertFalse(result['semantic_support_claimed'])
        for record in self.adapter.records: audit_messages(record['messages'])

    def test_false_pass_stops_after_first_control_without_next_request(self):
        self.transport.force_first_pass = True
        result = self.run_batch()
        self.assertIn('WorkingControlUnexpectedSemantic',result['stop_reason'])
        self.assertEqual(result['calls'],1)
        self.assertEqual([r['execution'] for r in result['rows'][1:]],['NOT_RUN']*9)

    def test_first_provider_failure_stops_without_retry(self):
        self.transport.fail_call = 1
        result = self.run_batch()
        self.assertEqual(result['calls'],1)
        self.assertEqual(len(self.transport.wires),1)
        self.assertEqual(result['rows'][1]['execution'],'NOT_RUN')

    def test_call_budget_prevents_an_extra_transport_invocation(self):
        self.config['budget']['max_calls']=1
        result = self.run_batch()
        self.assertIn('WorkingCallBudgetExhausted',result['stop_reason'])
        self.assertEqual(len(self.transport.wires),1)

    def test_deadline_prevents_first_transport_invocation(self):
        values = iter([0,901])
        result = self.run_batch(clock=lambda:next(values))
        self.assertIn('WorkingDeadlineExhausted',result['stop_reason'])
        self.assertEqual(len(self.transport.wires),0)

    def test_remaining_deadline_caps_inflight_timeout_and_late_return_stops(self):
        self.transport.spec = self.config['fixed_review_controls'][0]
        budget = CallBudget(self.adapter,{**self.config['budget'],'wall_time_seconds':5},clock=iter([0,4,6]).__next__)
        budget.begin_case(2)
        world = WorkingWorld(EvidenceRecorder(self.directory/'late.jsonl'),self.config,self.config['normal_cases'][1],fixed_control=True)
        self.addCleanup(world.e.close)
        with self.assertRaisesRegex(ModelFailure,'WorkingDeadlineReachedAfterCall'):
            world.run_control(self.config['fixed_review_controls'][0],budget)
        self.assertEqual(self.transport.wires[0]['timeout'],1)

    def test_failed_observation_never_generates_policy_and_turn_closes(self):
        self.transport.before_case(self.config['normal_cases'][0])
        self.transport.fail_call=2
        evidence=EvidenceRecorder(self.directory/'observation-failure.jsonl');self.addCleanup(evidence.close)
        world=WorkingWorld(evidence,self.config,self.config['normal_cases'][0])
        budget=CallBudget(self.adapter,self.config['budget']);budget.begin_case(8)
        with self.assertRaises(ModelFailure):world.run_normal(budget)
        world.close_failure()
        self.assertEqual(self.adapter.calls,2)
        self.assertTrue(all(r['purpose']!='PolicyOutcomeGeneration' for r in self.adapter.records))
        self.assertEqual(world.sessions.turns[world.turn]['phase'],'SETTLED')
        self.assertFalse(world.sessions.active)
        self.assertFalse(any(r.ref.identity=='WorkingObservation' for r in world.h.states.records()))

    def test_no_intervention_settles_without_creating_effect(self):
        self.transport.normal_outcome='NoIntervention'
        self.transport.before_case(self.config['normal_cases'][0])
        evidence=EvidenceRecorder(self.directory/'no-intervention.jsonl');self.addCleanup(evidence.close)
        world=WorkingWorld(evidence,self.config,self.config['normal_cases'][0])
        budget=CallBudget(self.adapter,self.config['budget']);budget.begin_case(8)
        result=world.run_normal(budget)
        self.assertEqual(result['outcome'],'NoIntervention')
        self.assertEqual(world.sessions.turns[world.turn]['phase'],'SETTLED')
        self.assertFalse(any(r.kind=='ActionIntent' for r in world.h.executions.records()))

    def test_host_only_values_are_absent_from_all_actual_messages(self):
        for spec in self.config['normal_cases']:spec['required_content']=['RUNTIME_HOST_ONLY_SENTINEL']
        for spec in self.config['fixed_review_controls']:spec['required_detection']='RUNTIME_HOST_ONLY_SENTINEL'
        result=self.run_batch()
        self.assertIsNone(result['stop_reason'])
        for record in self.adapter.records:audit_messages(record['messages'])

    def test_audit_rejects_host_labels_in_wire(self):
        with self.assertRaises(AssertionError):audit_messages([{'role':'user','content':'{"expected_semantic":"FAIL"}'}])
