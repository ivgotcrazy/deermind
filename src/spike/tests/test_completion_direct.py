"""Exact profile binding and refusal of an unvalidated explanation; scripted semantics."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from foundation.cases import EvidenceRecorder
from foundation.exit_campaign import ExitBudget, close_world
from foundation.llm import LLMConfig
from foundation.runtime import ContractError
from foundation.semantic_review import check_criteria_review
from run_completion_direct import DirectWorld, DirectTransport, make_plan
from run_network_retry import NetworkRetryAdapter


class CompletionDirectTests(unittest.TestCase):
    def world(self, fail_explanation=False):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        e=EvidenceRecorder(Path(directory.name)/'evidence.jsonl');self.addCleanup(e.close)
        transport=DirectTransport()
        def response(url,key,wire,timeout):
            result=transport(url,key,wire,timeout)
            if fail_explanation and 'REQUIRED ACTION CONTENT CHECK:' in wire['messages'][0]['content']:
                function=result['choices'][0]['message']['tool_calls'][0]['function']
                function['arguments']=json.dumps({'status':'FAIL','rationale':'Scripted ActionSemantic content failure.'})
            return result
        adapter=NetworkRetryAdapter(LLMConfig('OFFLINE',base_url='https://api.deepseek.com/beta',max_calls=60,
            max_output_tokens=4096,max_input_chars=64000),response,sleep=lambda _:None)
        limited=ExitBudget(adapter,make_plan()['budget']);limited.begin_case(60);limited.case_id='test'
        world=DirectWorld(e);queued=[False]
        def inject():
            if not queued[0]:queued[0]=True;world.queue_teaching()
        limited.before_request=inject
        return world,e,adapter,limited

    def test_explanation_has_required_exact_profile_before_intent_and_new_task_uses_own_math(self):
        w,e,a,limited=self.world()
        self.assertEqual(w.run_path(limited)['coverage'],'COMPLETE')
        self.assertEqual(a.calls,20)
        checks=[r for r in w.h.executions.records() if r.kind=='SemanticValidationExecution'
            and r.payload['protocol']['identity']=='CompletionX5ActionSemanticPolicy']
        self.assertEqual(len(checks),1)
        self.assertFalse(checks[0].payload['fixture'])
        intent=next(r for r in w.h.executions.records() if r.kind=='ActionIntent'
            and r.payload['action_semantic_ref']['identity']=='RevealFullSolution')
        self.assertLessEqual(checks[0].recorded_at,intent.recorded_at)
        p=w.h.get(w.protocols['new-work'].ref).payload
        self.assertEqual(p['arithmetic_fixture'],{'60 / 10':6,'6 * 7':42,'60 / 10 * 7':42})
        self.assertTrue(all(c['passed'] for c in e.checks))

    def test_failed_action_content_review_never_creates_explanation_intent_or_exposure(self):
        w,e,a,limited=self.world(True)
        with self.assertRaisesRegex(ContractError,'X5-P-explain:ValidationFailed'):
            w.run_path(limited)
        self.assertEqual(w.h.get(w.activity).payload['activity_purpose'],'Teaching')
        self.assertFalse(any(r.kind=='ActionIntent' and r.payload['action_semantic_ref']['identity']=='RevealFullSolution'
            for r in w.h.executions.records()))
        self.assertFalse(any(r.kind=='ActionOccurrence' for r in w.h.facts.records()))
        close_world(w,e)
        self.assertFalse(w.sessions.active)

    def test_direct_review_cannot_omit_criterion_or_replace_exact_quotation(self):
        criteria=[{'id':'meaning','evidence_mode':'positive_support'}]
        value={'reviewed_fields':['description'],'criteria':[{'id':'meaning','status':'PASS',
            'quotes':[{'field':'description','text':'exact'}],'rationale':'Scripted.'}]}
        self.assertEqual(check_criteria_review(value,{'description':'exact'},criteria)[0],'PASS')
        missing=deepcopy(value);missing['criteria']=[]
        with self.assertRaisesRegex(ContractError,'IncompleteCriterionCoverage'):
            check_criteria_review(missing,{'description':'exact'},criteria)
        changed=deepcopy(value);changed['criteria'][0]['quotes'][0]['text']='replacement'
        with self.assertRaisesRegex(ContractError,'QuoteNotInExactCandidate'):
            check_criteria_review(changed,{'description':'exact'},criteria)


if __name__=='__main__':unittest.main()
