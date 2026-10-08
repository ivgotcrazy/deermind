from copy import deepcopy
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import Mock

from foundation.llm import LLMConfig, ModelFailure
from foundation.cases import EvidenceRecorder
from foundation.single_task import run_batch
from run_network_retry import NetworkRetryAdapter, select_plan, RETRYABLE
from test_single_task_v2 import IndexedScriptedTransport

ROOT=Path(__file__).parents[1]


def response(content='{"status":"FAIL"}'):
    return {'choices':[{'finish_reason':'stop','message':{'content':content}}]}


class NetworkRetryTests(unittest.TestCase):
    def test_transport_retry_preserves_exact_request_and_keeps_failed_attempt(self):
        wire=Mock(side_effect=[ModelFailure('ProviderTLSFailure'),response()])
        sleeps=[];adapter=NetworkRetryAdapter(LLMConfig('test',max_calls=3),wire,sleep=sleeps.append)
        adapter.begin_turn('T01',1)
        messages=[{'role':'user','content':'Fixed original input'}]
        value,_=adapter.complete(messages,'test')
        self.assertEqual(value,{'status':'FAIL'})
        self.assertEqual(adapter.calls,2);self.assertEqual(adapter.logical_calls,1)
        self.assertEqual([r['status'] for r in adapter.records],['FAILED','COMPLETED'])
        self.assertEqual([r['request_attempt'] for r in adapter.records],[1,2])
        self.assertEqual(wire.call_args_list[0].args[2],wire.call_args_list[1].args[2])
        self.assertEqual(sleeps,[2])

    def test_semantic_fail_and_invalid_model_output_never_retry(self):
        for returned in (response(),response('not JSON'),response('')):
            wire=Mock(return_value=returned);sleep=Mock()
            adapter=NetworkRetryAdapter(LLMConfig('test'),wire,sleep=sleep)
            try:adapter.complete([],'test')
            except ModelFailure:pass
            self.assertEqual(wire.call_count,1);sleep.assert_not_called()

    def test_three_failed_attempts_stop_and_remain_visible(self):
        wire=Mock(side_effect=ModelFailure('ProviderIncompleteRead'));sleeps=[]
        adapter=NetworkRetryAdapter(LLMConfig('test',max_calls=10),wire,sleep=sleeps.append)
        with self.assertRaisesRegex(ModelFailure,'ProviderIncompleteRead'):adapter.complete([],'test')
        self.assertEqual(adapter.calls,3);self.assertEqual(len(adapter.records),3)
        self.assertEqual(sleeps,[2,5])

    def test_call_budget_and_wall_deadline_prevent_extra_attempts(self):
        wire=Mock(side_effect=ModelFailure('ProviderTimeout'))
        adapter=NetworkRetryAdapter(LLMConfig('test',max_calls=1),wire,sleep=lambda _:None)
        with self.assertRaisesRegex(ModelFailure,'BudgetExhausted'):adapter.complete([],'test')
        self.assertEqual(wire.call_count,1)
        wire.reset_mock();sleep=Mock()
        adapter=NetworkRetryAdapter(LLMConfig('test',max_calls=3),wire,clock=lambda:0,deadline=1,sleep=sleep)
        with self.assertRaisesRegex(ModelFailure,'DeadlineExhausted'):adapter.complete([],'test')
        self.assertEqual(wire.call_count,1);sleep.assert_not_called()
        self.assertEqual(wire.call_args.args[3],1)

    def test_nonretryable_errors_stop_without_wait(self):
        for code in ('ProviderHTTPError:400','ProviderHTTPError:401','OutputSchemaMismatch','InputLimitExceeded'):
            wire=Mock(side_effect=ModelFailure(code));sleep=Mock()
            adapter=NetworkRetryAdapter(LLMConfig('test'),wire,sleep=sleep)
            with self.assertRaises(ModelFailure):adapter.complete([],'test')
            self.assertEqual(wire.call_count,1);sleep.assert_not_called()

    def test_logical_seven_call_limit_is_separate_from_transport_attempts(self):
        wire=Mock(return_value=response());adapter=NetworkRetryAdapter(LLMConfig('test',max_calls=30),wire)
        for _ in range(7):adapter.complete([],'test')
        with self.assertRaisesRegex(ModelFailure,'WorkingCallBudgetExhausted'):adapter.complete([],'test')
        adapter.begin_turn('T01',2);adapter.complete([],'test')
        self.assertEqual(wire.call_count,8)

    def test_selects_only_nine_affected_sessions_and_retains_both_original_inputs(self):
        plan=json.loads((ROOT/'fixtures/single-task-prototype-v2.json').read_text(encoding='utf-8'))
        result=json.loads((ROOT/'runs/single-task-prototype-v2/results.json').read_text(encoding='utf-8'))
        old=deepcopy(plan);selected,targets=select_plan(plan,result)
        self.assertEqual(plan,old)
        self.assertEqual(len(targets),13)
        self.assertEqual([s['id'] for s in selected['sessions']],['T01','T02','T03','T05','T06','T07','T08','T09','T10'])
        self.assertTrue(all(s in plan['sessions'] for s in selected['sessions']))
        self.assertEqual(selected['budget']['max_calls'],378)

    def test_full_selected_batch_logs_retries_and_continues_after_schema_failure(self):
        plan=json.loads((ROOT/'fixtures/single-task-prototype-v2.json').read_text(encoding='utf-8'))
        original=json.loads((ROOT/'runs/single-task-prototype-v2/results.json').read_text(encoding='utf-8'))
        plan,_=select_plan(plan,original)
        scripted=IndexedScriptedTransport()
        attempts=[]
        def wire(url,key,payload,timeout):
            attempts.append(payload)
            if len(attempts)==1:raise ModelFailure('ProviderTLSFailure')
            if len(attempts)==6:raise ModelFailure('OutputSchemaMismatch')
            return scripted(url,key,payload,timeout)
        adapter=NetworkRetryAdapter(LLMConfig('OFFLINE-ONLY',base_url=plan['model']['base_url'],max_calls=378),
                                    wire,sleep=lambda _:None)
        def before(spec,number):
            adapter.begin_turn(spec['id'],number)
            scripted.before_turn(spec,number)
        with tempfile.TemporaryDirectory() as directory:
            result=run_batch(plan,adapter,lambda name:EvidenceRecorder(Path(directory)/(name+'.jsonl')),
                             before_turn=before)
            turns=[t for row in result['rows'] for t in row['turns']]
            self.assertIsNone(result['stop_reason'])
            self.assertEqual(len(turns),18)
            self.assertEqual(turns[0]['reason'],'ModelFailure:OutputSchemaMismatch')
            self.assertTrue(all(t['execution']=='COMPLETED' for t in turns[1:]))
            events=[json.loads(line) for path in Path(directory).glob('*.jsonl')
                    for line in path.read_text(encoding='utf-8').splitlines()]
            calls=[e for e in events if e['kind']=='model_execution']
            self.assertEqual(len(calls),adapter.calls)
            self.assertEqual(calls[0]['status'],'FAILED')
            self.assertEqual(calls[1]['request_attempt'],2)
            self.assertEqual(attempts[0],attempts[1])
            self.assertEqual(sum(r['status']=='FAILED' for r in adapter.records),2)


if __name__=='__main__':unittest.main()
