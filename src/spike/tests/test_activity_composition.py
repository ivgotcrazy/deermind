"""Local deterministic transports test mechanisms, never semantic quality."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from foundation.activity_cases import ActivityWorld, ROOT, run_boundary
from foundation.actions import exact_ref
from foundation.cases import EvidenceRecorder
from foundation.llm import LLMConfig
from foundation.records import json_value
from foundation.runtime import ContractError, CurrentResolver
from run_activity_composition_validation import execute_path, load_design


def transport(url,key,wire,timeout):
    name=wire['tool_choice']['function']['name']
    context=json.loads(wire['messages'][1]['content'])
    if name=='submit_observation':value={'description':'Explicit scripted local test Observation.'}
    elif name=='submit_policy':
        envelope=next(i['content'] for i in context if i['kind']=='ActivityConstraints')
        action=next((i for i in context if i['kind']=='ActionSemantic'),None)
        value={'outcome':'Execute' if action else 'NoIntervention','action_identity':action['ref']['identity'] if action else '',
            'action_revision':action['ref']['revision'] if action else '', 'exact_payload':action['content']['exact_payload'] if action else '',
            'executor_target':action['content']['executor_target'] if action else '', 'episode':envelope['episode'],
            'rationale':'SCRIPTED LOCAL TRANSPORT ONLY','context_refs':[context[0]['ref']],
            'expected_disclosure':'SCRIPTED','uncertainty':'SCRIPTED','defer_condition':''}
    else:value={'status':'PASS','rationale':'Scripted mechanism fixture; not real validation.'}
    return {'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[
        {'id':'test-call','type':'function','function':{'name':name,'arguments':json.dumps(value)}}]}}]}


class LocalWorld(ActivityWorld):
    def install_protocol(self,name,kind,path,inputs):
        if kind=='Observation':
            definition=json.loads(path.read_text(encoding='utf-8'))
            validation=json.loads((ROOT/'protocols/policy-x5-v1.json').read_text(encoding='utf-8'))['output_contracts']['validation']
            # A different, explicitly local fixture protocol; production v11 is untouched.
            definition={k:definition[k] for k in ('generation_system','validation_system')}
            definition.update(validation_format='legacy-v1',output_contracts={
                'generation':json.loads(path.read_text(encoding='utf-8'))['output_contracts']['generation'],'validation':validation})
            with tempfile.TemporaryDirectory() as directory:
                p=Path(directory)/'local-only.json';p.write_text(json.dumps(definition),encoding='utf-8')
                return super().install_protocol(name,kind,p,inputs)
        return super().install_protocol(name,kind,path,inputs)


class ActivityCompositionTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup);self.directory=Path(d.name)
        self.e=EvidenceRecorder(self.directory/'test.jsonl');self.addCleanup(self.e.close)
        self.config=LLMConfig('local-only',base_url='https://api.deepseek.com/beta',max_calls=28,max_output_tokens=3072)

    def complete(self):
        row,snapshots=execute_path(self.e,1,self.config,transport,LocalWorld)
        self.assertEqual(row['result'],'PASS',row)
        return snapshots

    def test_full_path_and_four_effect_boundaries(self):
        snapshots=self.complete()
        for variant in load_design()['boundaries']:
            e=EvidenceRecorder(self.directory/(variant+'.jsonl'))
            try:row=run_boundary(snapshots['switch-teaching' if variant=='control-not-occurred' else 'explain'],e,variant)
            finally:e.close()
            self.assertEqual(row['result'],'PASS',row)

    def test_control_requires_result_processing_and_preserves_history(self):
        w=self.complete()['switch-teaching'];w.e=self.e
        old=w.activity
        with self.assertRaisesRegex(ContractError,'TurnPhaseMismatch'):w.sessions.continue_cycle(w.current_turn)
        with self.assertRaisesRegex(ContractError,'DisplayExecutorMismatch'):w.actions.execute(w.tokens['interaction'],w.current_intent)
        result=w.effect(w.current_turn,w.current_intent)
        self.assertEqual(result['status'],'Occurred')
        self.assertIsNone(w.h.get(w.activity).corrects)
        w.allow_reads()
        resolution=CurrentResolver(w.h.capture(),w.runtime._eligibility(w.tokens['interaction'],'reasoning-runtime')).resolve_exact(old,'learner-A','learning')
        self.assertEqual(resolution.reason,'ActivitySuperseded')
        w.sessions.continue_cycle(w.current_turn)
        self.assertEqual(w.sessions.turns[w.current_turn]['phase'],'INPUT')
        with self.assertRaisesRegex(ContractError,'ConversationTurnActive'):w.sessions.start('X5')

    def test_stale_policy_cannot_create_another_intent_after_switch(self):
        w=self.complete()['switch-teaching'];w.e=self.e
        policy=exact_ref(w.h.get(w.current_intent).payload['policy_ref'])
        w.effect(w.current_turn,w.current_intent);w.allow_reads()
        with self.assertRaisesRegex(ContractError,'ActivitySuperseded'):
            w.actions.create_intent(w.tokens['interaction'],policy,expires_at=w.h.clock.now+100,idempotency_key='another')

    def test_no_intervention_does_not_fabricate_control_stage(self):
        def decline(url,key,wire,timeout):
            result=transport(url,key,wire,timeout)
            if wire['tool_choice']['function']['name']=='submit_policy':
                fn=result['choices'][0]['message']['tool_calls'][0]['function'];value=json.loads(fn['arguments'])
                value.update(outcome='NoIntervention',action_identity='',action_revision='',exact_payload='',executor_target='')
                fn['arguments']=json.dumps(value)
            return result
        row,snapshots=execute_path(self.e,1,self.config,decline,LocalWorld)
        self.assertEqual(row['coverage'],'INCOMPLETE');self.assertEqual(snapshots,{})
        self.assertEqual(row['failed_checks'],[])

    def test_model_failure_not_retried_or_replaced_with_script(self):
        count=[]
        def broken(*args):count.append(1);raise TimeoutError()
        row,snapshots=execute_path(self.e,1,self.config,broken,LocalWorld)
        self.assertEqual(len(count),1);self.assertEqual(row['model_calls'],1)
        self.assertEqual(row['coverage'],'INCOMPLETE');self.assertEqual(snapshots,{})

    def test_display_result_cannot_continue_control_cycle(self):
        w=self.complete()['explain'];w.e=self.e
        w.effect(w.current_turn,w.current_intent)
        with self.assertRaisesRegex(ContractError,'SuccessfulControlRequired'):w.sessions.continue_cycle(w.current_turn)


if __name__=='__main__':unittest.main()
