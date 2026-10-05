import copy
import json
from pathlib import Path
import tempfile
import unittest

from foundation.cases import EvidenceRecorder
from foundation.formation_cases import FormationWorld, run_case
from foundation.llm import DeepSeekAdapter, LLMConfig
from foundation.protocol_preflight import check_observation_contract
from run_formation_validation import ROOT, load_design, summarize


class FormationTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup);self.directory=Path(d.name)
        self.fixture,self.definition=load_design()

    def test_all_variants_share_active_protocol_and_exclude_readable_history(self):
        for variant in self.fixture['variants']:
            e=EvidenceRecorder(self.directory/(variant['id']+'.jsonl'))
            try:
                w=FormationWorld(self.definition,variant);w.check_exclusion(e)
                self.assertTrue(all(c['passed'] for c in e.checks),e.checks)
                self.assertEqual(w.context.protocol.identity,self.definition['identity'])
                self.assertEqual(w.h.get(w.work).payload['text'],variant['text'])
                self.assertEqual(w.context.versions.semantic_bindings,(w.protocol,w.rule,w.semantics))
            finally:e.close()

    def test_preflight_rejects_actual_x5_defect_and_accepts_explicit_repair(self):
        old=json.loads((ROOT/'protocols/observation-x5-request-v1.json').read_text(encoding='utf-8'))
        new=json.loads((ROOT/'protocols/observation-x5-request-v2.json').read_text(encoding='utf-8'))
        with self.assertRaisesRegex(ValueError,'CriterionSchemaMismatch'):check_observation_contract(old)
        self.assertEqual(check_observation_contract(new)['status'],'PASS')

    def test_preflight_rejects_missing_and_duplicate_criteria_and_roles(self):
        for mutation in ('criterion','duplicate','role'):
            definition=copy.deepcopy(self.definition)
            if mutation=='criterion':definition['criteria'][0]['id']='undeclared'
            elif mutation=='duplicate':definition['criteria'].append(definition['criteria'][0])
            else:definition['responsibility_admission'].pop('uncertain')
            with self.assertRaises(ValueError):check_observation_contract(definition)

    def test_failed_provider_is_not_retried_or_counted_as_supported(self):
        count=[]
        def broken(*args):count.append(1);raise TimeoutError()
        e=EvidenceRecorder(self.directory/'failed.jsonl')
        try:row=run_case(e,self.definition,self.fixture['variants'][0],1,
            DeepSeekAdapter(LLMConfig('local-only',base_url=self.definition['provider_endpoint'],max_calls=4),broken))
        finally:e.close()
        self.assertEqual(len(count),1);self.assertEqual(row['model_calls'],1)
        self.assertIsNone(row['commit_status']);self.assertEqual(row['result'],'NON_SUCCESS')
        summary=summarize([row],self.fixture)
        self.assertEqual(summary['not_run'],14);self.assertEqual(summary['matched_runs'],0)

    def test_local_transport_only_formal_success_and_rejection(self):
        # Different explicit test-only protocol; no semantic capability claim.
        definition=copy.deepcopy(self.definition)
        definition['validation_format']='legacy-v1';definition.pop('responsibility_profile')
        for key in ('source_encoding','claim_axes','inspection_encoding'):definition.pop(key,None)
        definition['output_contracts']['validation']=json.loads((ROOT/'protocols/policy-e1-v1.json').read_text(encoding='utf-8'))['output_contracts']['validation']
        for status in ('PASS','FAIL','UNRESOLVED'):
            def transport(url,key,wire,timeout):
                name=wire['tool_choice']['function']['name']
                output={'description':'Explicit local mechanism fixture, not real cognition.'} if name=='submit_observation' else {'status':status,'rationale':'Explicit local fixture review.'}
                return {'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[
                    {'type':'function','function':{'name':name,'arguments':json.dumps(output)}}]}}]}
            e=EvidenceRecorder(self.directory/(status+'.jsonl'))
            try:row=run_case(e,definition,self.fixture['variants'][0],1,
                DeepSeekAdapter(LLMConfig('local-only',base_url=definition['provider_endpoint'],max_calls=4),transport))
            finally:e.close()
            self.assertEqual(row['commit_status'],'Committed' if status=='PASS' else 'ValidationFailed',row)
            self.assertEqual(row['failed_checks'],[])


if __name__=='__main__':unittest.main()
