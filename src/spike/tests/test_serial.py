from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from foundation.cases import EvidenceRecorder
from foundation.llm import LLMConfig
from foundation.records import Ref,Space,json_value
from foundation.runtime import ContractError
from foundation.serial_cases import SerialWorld
from run_serial_validation import execute_branch,load_design


def transport(url,key,wire,timeout):
    name=wire['tool_choice']['function']['name']
    if name=='submit_policy':
        context=json.loads(wire['messages'][1]['content'])
        value={'outcome':'Execute','action_identity':'HintCheckStep','action_revision':'e1-v1',
            'exact_payload':'再检查一下 42÷6。','executor_target':'mock-display','episode':'apple-episode',
            'rationale':'Synthetic transport fixture; not a semantic evaluation.',
            'context_refs':[context[0]['ref']],'expected_disclosure':'Local step cue.',
            'uncertainty':'Fixture.','defer_condition':''}
    else:value={'status':'PASS','rationale':'Synthetic validation for deterministic interleaving tests.'}
    return {'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[
        {'id':'test-call','type':'function','function':{'name':name,'arguments':json.dumps(value)}}]}}]}


class SerialTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.directory=Path(directory.name)
        self.e=EvidenceRecorder(self.directory/'base.jsonl');self.addCleanup(self.e.close)
        self.fixture,self.policy,self.definition=load_design()
        self.base=SerialWorld(self.e,self.definition,self.policy)

    def test_declared_interleavings_use_shared_initial_snapshot_and_formal_commits(self):
        initial=self.base.h.capture()
        for branch in self.fixture['branches']:
            e=EvidenceRecorder(self.directory/(branch+'.jsonl'))
            try:row=execute_branch(self.base,e,branch,1,LLMConfig('test-key',base_url=self.definition['provider_endpoint'],max_calls=self.fixture['branch_call_limits'][branch]),transport)
            finally:e.close()
            self.assertEqual(row['result'],'PASS',row)
            self.assertEqual(self.base.h.states.records(),initial.states.records())

    def test_early_settle_and_next_start_are_rejected(self):
        self.base.queue_second()
        with self.assertRaisesRegex(ContractError,'TurnPhaseMismatch'):self.base.sessions.settle(self.base.turn)
        with self.assertRaisesRegex(ContractError,'ConversationTurnActive'):self.base.sessions.start('C')

    def test_current_head_requirement_rejects_old_basis_at_new_context_assembly(self):
        self.base.external_update()
        # A new turn cannot bind old r1 as a current-head input, although r1 still exists.
        self.base.sessions.turns[self.base.turn]['phase']='INPUT'
        with self.assertRaisesRegex(ContractError,'RequiredHeadChanged'):
            self.base.make_context(self.base.turn,self.base.input)
        self.assertIsNotNone(self.base.h.get(self.base.belief))

    def test_other_conversation_can_start_while_current_conversation_is_active(self):
        from foundation.cases import seed
        ref=seed(self.base.h,Ref(Space.FACT,'other-input','1'),kind='CurrentInteractionInput',payload={'text':'other input'})
        self.base.sessions.enqueue('C-other',ref)
        other=self.base.sessions.start('C-other')
        self.assertEqual(len(self.base.sessions.active),2)
        self.assertNotEqual(other,self.base.turn)

    def test_duplicate_input_and_wrong_context_are_rejected(self):
        with self.assertRaisesRegex(ContractError,'InputAlreadyEnqueued'):
            self.base.sessions.enqueue('C',self.base.input)
        self.base.queue_second()
        self.base.sessions.turns[self.base.turn]['phase']='INPUT'
        # An active turn cannot adopt the queued input as its own Context.
        wrong=self.base.make_context(self.base.turn,self.base.second_input)
        with self.assertRaisesRegex(ContractError,'TurnContextInputMismatch'):
            self.base.sessions.bind_context(self.base.turn,wrong)

    def test_real_policy_nonexecute_does_not_get_fabricated_effect_coverage(self):
        def no_action(url,key,wire,timeout):
            result=transport(url,key,wire,timeout)
            if wire['tool_choice']['function']['name']=='submit_policy':
                function=result['choices'][0]['message']['tool_calls'][0]['function'];p=json.loads(function['arguments'])
                p.update(outcome='NoIntervention',action_identity='',action_revision='',exact_payload='',executor_target='')
                function['arguments']=json.dumps(p)
            return result
        e=EvidenceRecorder(self.directory/'no-action.jsonl')
        try:row=execute_branch(self.base,e,'C-external-before-effect',1,LLMConfig('test-key',base_url=self.definition['provider_endpoint'],max_calls=2),no_action)
        finally:e.close()
        self.assertEqual(row['coverage'],'INCOMPLETE');self.assertEqual(row['result'],'NON_SUCCESS')


if __name__=='__main__':unittest.main()
