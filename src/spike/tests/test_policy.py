import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter, LLMConfig
from foundation.policy import policy_legality
from foundation.policy_cases import PolicyWorld, negative_fixture, run_policy_case
from foundation.records import json_value
from foundation.runtime import ContractError
from run_policy_validation import load_design


def response(value,name):
    return {'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[
        {'id':'test-call','type':'function','function':{'name':name,'arguments':json.dumps(value)}}]}}]}


class PolicyTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.e=EvidenceRecorder(Path(directory.name)/'evidence.jsonl');self.addCleanup(self.e.close)
        self.fixture,self.definition=load_design()
        self.w=PolicyWorld(self.e,self.definition,self.fixture,self.fixture['variants'][0])

    def payload(self,outcome='Execute'):
        return {'outcome':outcome,'action_identity':'HintCheckStep' if outcome=='Execute' else '',
            'action_revision':'e1-v1' if outcome=='Execute' else '',
            'exact_payload':'再检查一下 42÷6。' if outcome=='Execute' else '',
            'executor_target':'mock-display' if outcome=='Execute' else '', 'episode':self.w.episode,
            'rationale':'Synthetic policy output for transport tests, not a semantic judgment.',
            'context_refs':[json_value(self.w.work)],'expected_disclosure':'A local step cue.' if outcome=='Execute' else 'None.',
            'uncertainty':'Use of help is unknown.','defer_condition':'On the next learner submission.' if outcome=='Defer' else ''}

    def adapter(self,payload,semantic='PASS',utility='PASS'):
        scores={'scores':[{'id':k,'status':utility,'reason':'Synthetic transport control.'} for k in self.definition['utility_rubric']]}
        transport=Mock(side_effect=[response(payload,'submit_policy'),response({'status':semantic,'rationale':'Synthetic validation.'},'submit_review'),response(scores,'submit_policy_utility')])
        return DeepSeekAdapter(LLMConfig('test-key',base_url=self.definition['provider_endpoint'],max_calls=3),transport)

    def test_real_adapter_path_uses_distinct_generation_validation_and_test_review(self):
        adapter=self.adapter(self.payload())
        row=run_policy_case(self.e,self.definition,self.fixture,self.fixture['variants'][0],1,adapter)
        self.assertEqual(row['result'],'PASS');self.assertEqual(row['effect_status'],'Occurred')
        self.assertEqual([r['purpose'] for r in adapter.records],['PolicyOutcomeGeneration','PolicyOutcomeSemanticValidation','PolicyUtilityReview'])
        self.assertEqual(len({r['execution_id'] for r in adapter.records}),3)
        self.assertTrue(all(len(json.dumps(r['messages'],ensure_ascii=False))<16000 for r in adapter.records))

    def test_utility_failure_is_measurement_not_runtime_authority(self):
        row=run_policy_case(self.e,self.definition,self.fixture,self.fixture['variants'][0],1,self.adapter(self.payload(),utility='FAIL'))
        self.assertEqual(row['utility_status'],'FAIL');self.assertEqual(row['commit_status'],'Committed')
        self.assertEqual(row['effect_status'],'Occurred');self.assertEqual(row['result'],'NON_SUCCESS')

    def test_semantic_failure_cannot_be_overridden_by_utility_pass(self):
        row=run_policy_case(self.e,self.definition,self.fixture,self.fixture['variants'][0],1,self.adapter(self.payload(),semantic='FAIL'))
        self.assertEqual(row['utility_status'],'PASS');self.assertEqual(row['commit_status'],'ValidationFailed')
        self.assertIsNone(row['effect_status'])

    def test_nonintervention_and_defer_form_outcomes_without_intent(self):
        for outcome in ('NoIntervention','Defer'):
            row=run_policy_case(self.e,self.definition,self.fixture,self.fixture['variants'][0],1,self.adapter(self.payload(outcome)))
            self.assertEqual(row['result'],'PASS');self.assertIsNone(row['effect_status'])

    def test_inadmissible_full_solution_is_rejected_at_shared_commit(self):
        self.assertTrue(negative_fixture(self.e,self.definition,self.fixture))

    def test_parameters_context_refs_and_defer_shape_are_checked_without_meaning(self):
        p=self.payload();p['exact_payload']='Answer is 105'
        self.assertEqual(policy_legality(p,self.w.context),'ExactActionParametersMismatch')
        p=self.payload();p['context_refs'][0]['revision']='missing'
        self.assertEqual(policy_legality(p,self.w.context),'PolicyContextReferenceInvalid')
        p=self.payload('Defer');p['defer_condition']=''
        self.assertEqual(policy_legality(p,self.w.context),'DeferConditionShapeInvalid')

    def test_wait_request_does_not_hardcode_a_pedagogical_outcome(self):
        wait=PolicyWorld(self.e,self.definition,self.fixture,self.fixture['variants'][2])
        self.assertEqual(policy_legality(self.payload(),wait.context),'')
        # Whether executing a hint responds well to this request belongs to the LLM rubric.

    def test_test_review_cannot_be_used_as_semantic_validation(self):
        candidate=self.w.runtime.propose(self.w.context,'P','r1',self.payload())
        self.assertEqual(self.w.runtime.commit(self.w.tokens['interaction'],candidate,'utility-review-id').reason,
                         'RequiredSemanticValidationMissing')


if __name__=='__main__':
    unittest.main()
