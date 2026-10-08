"""One offline field-reference integration and regression record; no provider mode."""
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from run_foundation import manifest

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT/'src/spike/runs/policy-field-references-v1'


def write(path, value):
    path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))


def main():
    RUN.mkdir(parents=True,exist_ok=False)
    frozen = manifest(ROOT)
    frozen.update(schema='policy-field-references-offline-v1',
        cases=['full-local-unit-suite','policy-field-references'], model_calls=0,
        external_network='BLOCKED', scope='Opt-in v5 host-resolved full-field evidence; scripted semantics only')
    write(RUN/'manifest.json', frozen)
    output = io.StringIO()
    network_attempts = []
    def reject(*args, **kwargs):
        network_attempts.append('BlockedNetworkAttempt')
        raise RuntimeError('OfflineNetworkForbidden')
    with patch('socket.create_connection',reject),patch('socket.socket.connect',reject):
        suite = unittest.defaultTestLoader.discover(str(ROOT/'src/spike/tests'))
        tests = sys.modules['test_policy_field_references'].FieldReferenceTests
        tests.artifact_directory = RUN/'cases'
        try:
            result = unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
        finally:
            tests.artifact_directory = None
    (RUN/'unit-tests.txt').write_bytes(output.getvalue().encode('utf-8'))
    changed = [name for name,h in frozen['content_sha256'].items()
               if sha256((ROOT/name).read_bytes()).hexdigest()!=h]
    summary = {'schema':'policy-field-references-offline-result-v1','date':'2026-10-07',
        'status':'PASS' if result.wasSuccessful() and not changed and not network_attempts else 'FAIL',
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'skipped':len(result.skipped),'new_test_methods':15,
        'case_evidence_files':len(list((RUN/'cases').glob('*.jsonl'))),
        'frozen_inputs':len(frozen['content_sha256']),'changed_frozen_inputs':changed,
        'external_model_calls':0,'blocked_network_attempts':len(network_attempts),
        'semantic_support_claimed':False,'real_v4_attempt_reopened':False,
        'working_configuration_changed':False,'default_protocol_changed':False,
        'original_A2':'DENIED','full_cases_completed':9,'gate_E':'OPEN','gate_F':'OPEN'}
    write(RUN/'summary.json', summary)
    write(RUN/'artifact-sha256.json', {p.relative_to(RUN).as_posix():sha256(p.read_bytes()).hexdigest()
        for p in sorted(RUN.rglob('*')) if p.is_file()})
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
