"""Offline preparation only: scripted requests, frozen sources and local tests."""
import io
import json
from hashlib import sha256
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter, LLMConfig
from foundation.working_campaign import run_batch
from preflight_restricted_working import CONFIG, preflight
from run_foundation import manifest

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT/'src/spike/review-packages/restricted-working-v1'


def write(path, value):
    path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))


def main():
    ready = preflight()
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    PACK.mkdir(parents=True,exist_ok=False)
    (PACK/'cases').mkdir()
    frozen = manifest(ROOT)
    sys.path.insert(0,str(ROOT/'src/spike/tests'))
    from test_working_campaign import ScriptedTransport, audit_messages
    scripted = ScriptedTransport()
    adapter = DeepSeekAdapter(LLMConfig('OFFLINE-SCRIPTED',base_url=config['model']['provider_endpoint'],
        model=config['model']['model'],max_calls=config['budget']['max_calls'],
        max_output_tokens=config['model']['max_output_tokens'],timeout_seconds=config['model']['timeout_seconds']),scripted)
    network_attempts=[]
    def reject(*args,**kwargs):
        network_attempts.append('BlockedNetworkAttempt')
        raise RuntimeError('OfflineNetworkForbidden')
    output=io.StringIO()
    with patch('socket.socket.connect',reject),patch('socket.create_connection',reject):
        batch=run_batch(config,adapter,lambda id:EvidenceRecorder(PACK/'cases'/(id+'.jsonl')),
                        before_case=scripted.before_case)
        suite=unittest.defaultTestLoader.discover(str(ROOT/'src/spike/tests'))
        tests=unittest.TextTestRunner(stream=output,verbosity=1).run(suite)
    for record in adapter.records:audit_messages(record['messages'])
    changed=[name for name,h in frozen['content_sha256'].items() if sha256((ROOT/name).read_bytes()).hexdigest()!=h]
    write(PACK/'actual-requests.json',adapter.records)
    write(PACK/'scripted-results.json',batch)
    (PACK/'unit-tests.txt').write_bytes(output.getvalue().encode('utf-8'))
    passed=(tests.wasSuccessful() and batch['stop_reason'] is None and not changed and not network_attempts
            and batch['calls']==config['budget']['planned_calls'])
    summary={'status':'OFFLINE_INTEGRATION_PASS' if passed else 'FAIL','date':'2026-10-07',
        'scope':'Actual shared protocol/context/candidate/commit/effect integration with scripted semantics only',
        'normal_cases':ready['normal_cases'],'fixed_controls':ready['fixed_controls'],
        'scripted_adapter_calls':batch['calls'],'actual_outgoing_messages_audited':len(adapter.records),
        'external_model_calls':0,'blocked_network_attempts':len(network_attempts),
        'tests_run':tests.testsRun,'new_test_methods':10,'test_failures':len(tests.failures),
        'test_errors':len(tests.errors),'skipped':len(tests.skipped),
        'frozen_inputs_verified':len(frozen['content_sha256']),'changed_frozen_inputs':changed,
        'maximum_message_chars':max(len(json.dumps(r['messages'],ensure_ascii=False)) for r in adapter.records),
        'real_execution_started':False,'semantic_support_claimed':False,
        'original_A2':'DENIED','original_full_cases_completed':9,'gate_E':'OPEN','gate_F':'OPEN'}
    write(PACK/'summary.json',summary)
    write(PACK/'manifest.json',{'source_sha256':frozen['content_sha256'],
        'configuration_sha256':ready['configuration_sha256'],
        'artifact_sha256':{p.relative_to(PACK).as_posix():sha256(p.read_bytes()).hexdigest()
                           for p in sorted(PACK.rglob('*')) if p.is_file()},
        'external_model_calls':0,'semantic_labels_in_model_requests':False,
        'independent_semantic_review':False,'real_execution_started':False})
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
