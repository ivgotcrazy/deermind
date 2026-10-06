"""Offline v2 binding and actual adapter-message integration, not semantic evaluation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from foundation.cases import EvidenceRecorder
from foundation.policy_cases import PolicyWorld, run_policy_case
from foundation.records import Ref, Space, json_value
from foundation.runtime import ContractError
from run_policy_validation import load_design
import test_policy


class PolicyV2Tests(unittest.TestCase):
    artifact_directory = None
    payload = test_policy.PolicyTests.payload
    adapter = test_policy.PolicyTests.adapter

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        directory = self.artifact_directory or Path(temporary.name)
        directory.mkdir(parents=True, exist_ok=True)
        self.e = EvidenceRecorder(directory / (self._testMethodName + '.jsonl'))
        self.addCleanup(self.e.close)
        self.fixture, self.legacy = load_design()
        self.definition = json.loads((Path(__file__).resolve().parents[1] / 'protocols/policy-e1-v2.json').read_text(encoding='utf-8'))
        self.w = PolicyWorld(self.e,self.definition,self.fixture,self.fixture['variants'][0],rule_revision='v2')
        self.addCleanup(lambda: self.e.capture(self.w.h,'binding-world-final'))

    def run_case(self,semantic='PASS',utility='PASS',outcome='Execute'):
        adapter=self.adapter(self.payload(outcome),semantic,utility)
        row=run_policy_case(self.e,self.definition,self.fixture,self.fixture['variants'][0],1,adapter,rule_revision='v2')
        for record in adapter.records:
            self.e.emit('scripted_wire', **record)
        return row,adapter

    def test_three_exact_v2_bindings_and_actual_messages(self):
        bindings=self.w.context.versions.semantic_bindings
        self.assertEqual([(r.identity,r.revision) for r in bindings],
            [('E1PolicyProtocol','v2'),('E1PolicySemanticRules','v2'),('E1UtilityRules','v2')])
        row,adapter=self.run_case()
        self.assertEqual(row['result'],'PASS');self.assertEqual(row['effect_status'],'Occurred')
        self.assertEqual([r['purpose'] for r in adapter.records],
            ['PolicyOutcomeGeneration','PolicyOutcomeSemanticValidation','PolicyUtilityReview'])
        for record,key in zip(adapter.records,('generation_system','validation_system','utility_system')):
            self.assertEqual(record['messages'][0]['content'],self.definition[key])
            self.assertNotIn('developer_expected',json.dumps(record['messages']))
        utility=json.loads(adapter.records[2]['messages'][1]['content'])
        self.assertEqual(utility['rubric'],self.definition['utility_rubric'])
        self.assertEqual(self.w.h.get(self.w.utility_rule).payload['system'],self.definition['utility_system'])

    def test_v2_requires_explicit_entry_and_matching_declared_refs(self):
        with self.assertRaisesRegex(ContractError,'PolicyRuleRevisionMismatch'):
            PolicyWorld(self.e,self.definition,self.fixture,self.fixture['variants'][0])
        changed=copy.deepcopy(self.definition)
        changed['runtime_binding_requirement']['utility_rule_ref']['revision']='v1'
        with self.assertRaisesRegex(ContractError,'PolicyDeclaredBindingMismatch'):
            PolicyWorld(self.e,changed,self.fixture,self.fixture['variants'][0],rule_revision='v2')

    def test_legacy_entry_preserves_v1_bindings(self):
        w=PolicyWorld(self.e,self.legacy,self.fixture,self.fixture['variants'][0])
        self.assertEqual([r.revision for r in w.context.versions.semantic_bindings],['v1','v1'])
        self.assertEqual(w.utility_rule.revision,'v1')
        self.e.capture(w.h,'legacy-final')

    def test_utility_ref_substitution_rejected_before_provider_call(self):
        candidate=self.w.runtime.propose(self.w.context,'P','r1',self.payload())
        adapter=self.adapter(self.payload())
        self.w.policy_runtime.review_ref=Ref(Space.CANONICAL,'E1UtilityRules','v1')
        with self.assertRaisesRegex(ContractError,'PolicyUtilityVersionBindingMismatch'):
            self.w.policy_runtime.utility_review(self.w.tokens['interaction'],candidate,adapter)
        self.assertEqual(adapter.records,[])

    def test_semantic_fail_and_unresolved_block_commit_despite_utility_pass(self):
        for status in ('FAIL','UNRESOLVED'):
            row,_=self.run_case(semantic=status)
            self.assertNotEqual(row['commit_status'],'Committed')
            self.assertIsNone(row['effect_status']);self.assertEqual(row['utility_status'],'PASS')

    def test_utility_fail_cannot_revoke_effect_and_wait_outcomes_remain_available(self):
        row,_=self.run_case(utility='FAIL')
        self.assertEqual(row['commit_status'],'Committed');self.assertEqual(row['effect_status'],'Occurred')
        self.assertEqual(row['result'],'NON_SUCCESS')
        for outcome in ('NoIntervention','Defer'):
            row,_=self.run_case(outcome=outcome)
            self.assertEqual(row['result'],'PASS');self.assertIsNone(row['effect_status'])
