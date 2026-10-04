from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from foundation.cases import EvidenceRecorder, seed
from foundation.composition_cases import CompositionWorld
from foundation.llm import LLMConfig
from foundation.records import Record, Ref, Space, json_value
from foundation.runtime import ContractError, CurrentResolver
from run_composition_validation import execute_branch, load_design
from tests.test_serial import transport


class CompositionTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.directory=Path(tmp.name)
        self.e=EvidenceRecorder(self.directory/'base.jsonl');self.addCleanup(self.e.close)
        self.fixture,self.policy,self.definition=load_design()
        self.base=CompositionWorld(self.e,self.definition,self.policy)

    def run_branch(self,branch,provider=transport):
        e=EvidenceRecorder(self.directory/(branch+'.jsonl'))
        try:
            row=execute_branch(self.base,e,branch,1,LLMConfig('TEST',self.definition['provider_endpoint'],
                max_calls=self.fixture['branch_call_limits'][branch]),provider)
        finally:e.close()
        return row

    def test_three_complete_paths_preserve_baseline_and_bound_calls(self):
        initial=self.base.h.capture()
        for branch in self.fixture['branches']:
            row=self.run_branch(branch)
            self.assertEqual(row['result'],'PASS',row)
            self.assertEqual(row['model_calls'],self.fixture['branch_call_limits'][branch])
        self.assertEqual(self.base.h.states.records(),initial.states.records())
        self.assertEqual(self.base.h.canonical.activations(),initial.canonical.activations())

    def test_no_action_is_uncovered_not_a_fabricated_effect(self):
        def no_action(url,key,wire,timeout):
            result=transport(url,key,wire,timeout)
            if wire['tool_choice']['function']['name']=='submit_policy':
                fn=result['choices'][0]['message']['tool_calls'][0]['function'];p=json.loads(fn['arguments'])
                p.update(outcome='NoIntervention',action_identity='',action_revision='',exact_payload='',executor_target='')
                fn['arguments']=json.dumps(p)
            return result
        row=self.run_branch('X2-revoke',no_action)
        self.assertEqual(row['reason'],'RealPolicyDidNotSelectAction')
        self.assertEqual(row['coverage'],'INCOMPLETE')
        self.assertFalse(row['failed_checks'])

    def test_semantic_fail_is_coverage_gap_not_architecture_failure(self):
        def failed_review(url,key,wire,timeout):
            result=transport(url,key,wire,timeout)
            if wire['tool_choice']['function']['name']!='submit_policy':
                result['choices'][0]['message']['tool_calls'][0]['function']['arguments']=json.dumps({'status':'FAIL','rationale':'Test-only rejection.'})
            return result
        row=self.run_branch('X1-correction',failed_review)
        self.assertEqual(row['reason'],'SemanticReview:FAIL')
        self.assertEqual(row['coverage'],'INCOMPLETE')
        self.assertFalse(row['failed_checks'])

    def test_revocation_is_exact_scoped_and_preserves_historical_record(self):
        w=self.base;v1=w.x_protocols['v1'].ref;v2=w.x_protocols['v2'].ref
        old=w.h.get(v1)
        w.revoke_v1()
        resolve=lambda ref,scope='learner-A',purpose='learning': CurrentResolver(w.h.capture(),lambda *args:'').resolve_exact(ref,scope,purpose)
        self.assertEqual(resolve(v1).reason,'VersionIneligible')
        self.assertEqual(resolve(v2).current,v2)
        self.assertEqual(resolve(v1,purpose='historical-audit').current,v1)
        self.assertEqual(resolve(v1,scope='other-scope').current,v1)
        self.assertEqual(w.h.get(v1),old)

    def test_revocation_requires_canonical_target_and_existing_source(self):
        record=Record.create(ref=Ref(Space.FACT,'bad-revoke','1'),kind='VersionRevocationOccurred',subject='learner-A',
            owner='Evolution',recorded_at=self.base.h.clock.now,
            payload={'target':json_value(self.base.work),'source':json_value(self.base.input)})
        with self.assertRaisesRegex(ContractError,'InvalidVersionRevocationFixture'):
            self.base.h.seed_committed_fixture(record)
        record=replace(record,payload_json=json.dumps({'target':json_value(self.base.x_protocols['v1'].ref),
            'source':json_value(Ref(Space.EXECUTION,'missing','1'))}))
        with self.assertRaisesRegex(ContractError,'InvalidVersionRevocationFixture'):
            self.base.h.seed_committed_fixture(record)

    def test_failed_provider_does_not_advance_queued_turn(self):
        def fail(*args):raise TimeoutError()
        row=self.run_branch('X1-correction',fail)
        self.assertEqual(row['reason'],'ProviderTimeout')
        events=[json.loads(x) for x in (self.directory/'X1-correction.jsonl').read_text(encoding='utf-8').splitlines()]
        final=next(e for e in events if e['kind']=='snapshot' and e['label']=='branch_final')
        self.assertEqual(sum(r['kind']=='TurnStarted' for r in final['records']),1)
        self.assertFalse(any(r['kind']=='ActionIntent' for r in final['records']))


if __name__=='__main__':unittest.main()
