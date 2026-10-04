import json
from pathlib import Path
import tempfile
import unittest

from foundation.cases import EvidenceRecorder
from foundation.history_composition_cases import ReplayAuthorityWorld
from run_history_composition_validation import execute_case


class HistoryCompositionTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)

    def case(self,name):
        e=EvidenceRecorder(self.root/(name+'.jsonl'))
        try:result=execute_case(name,e)
        finally:e.close()
        return result,[json.loads(s) for s in (self.root/(name+'.jsonl')).read_text(encoding='utf-8').splitlines()]

    def test_correction_restores_chain_without_replaying_or_rewriting_hint(self):
        result,events=self.case('X3')
        self.assertEqual(result['result'],'PASS',result)
        snapshot=[e for e in events if e['kind']=='snapshot'][-1]
        self.assertEqual(sum(r['kind']=='ActionOccurrence' for r in snapshot['records']),1)
        self.assertEqual([r['revision'] for r in result['new_chain']],['r2']*3)
        self.assertEqual(next(e for e in events if e['kind']=='X3_stale_commit')['outcome']['reason'],'Corrected')

    def test_replay_denial_branches_keep_history_and_do_not_call_provider(self):
        result,events=self.case('X4')
        self.assertEqual(result['result'],'PASS',result)
        denied=[e for e in events if e['kind']=='X4_operation' and e['result']['capability']=='UNAVAILABLE']
        self.assertEqual(len(denied),6)
        self.assertTrue(all(not e['provider_inputs'] and not e['artifact_loads'] for e in denied))
        self.assertTrue(all(e['result']['historical_view'] is None and e['result']['generated_output'] is None for e in denied))
        self.assertEqual(sum(e['kind']=='X4_operation' and e['result']['capability']=='FULL' for e in events),8)

    def test_snapshot_branch_provider_and_bytes_are_isolated(self):
        e=EvidenceRecorder(self.root/'branch.jsonl');self.addCleanup(e.close)
        base=ReplayAuthorityWorld(e);a=base.branch(e);b=base.branch(e)
        a.replay_pair('one branch')
        self.assertEqual((base.calls,a.calls,b.calls),(0,1,0))
        self.assertEqual(base.artifacts.loads,[])
        self.assertEqual(b.artifacts.loads,[])


if __name__=='__main__':unittest.main()
