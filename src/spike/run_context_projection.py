"""Reserve one offline declared-field projection regression; no external provider calls."""
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from run_foundation import manifest


ROOT=Path(__file__).resolve().parent


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    directory=ROOT/'runs/context-projection-v1'
    directory.mkdir(parents=True,exist_ok=False)
    repo=ROOT.parents[1];frozen=manifest(repo)
    frozen.update(schema='context-projection-offline-v1',cases=['full-local-unit-suite','context-projection'],
        scope='Declared field-use projection, exact formal proof and actual local provider-wire exclusion; scripted semantics only',
        model_config=None,model_calls=0,external_network='BLOCKED')
    write(directory/'manifest.json',frozen)
    output=io.StringIO();network_attempts=[]
    def reject_network(*args,**kwargs):
        network_attempts.append('BlockedNetworkAttempt')
        raise RuntimeError('OfflineValidationNetworkDisabled')
    with patch('socket.create_connection',reject_network),patch('socket.socket.connect',reject_network):
        with redirect_stdout(output),redirect_stderr(output):
            suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
            tests=sys.modules['test_content_projection'].ContentProjectionTests
            tests.artifact_directory=directory/'cases'
            try:result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
            finally:tests.artifact_directory=None
    (directory/'unit-tests.txt').write_text(output.getvalue(),encoding='utf-8')
    changed=[p for p,h in frozen['content_sha256'].items() if sha256((repo/p).read_bytes()).hexdigest()!=h]
    artifacts={p.relative_to(directory).as_posix():sha256(p.read_bytes()).hexdigest() for p in sorted(directory.rglob('*')) if p.is_file()}
    summary={'schema':'context-projection-offline-result-v1',
        'status':'PASS' if result.wasSuccessful() and not changed and not network_attempts else 'FAIL',
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'projection_test_files':len(list((directory/'cases').glob('*.jsonl'))),
        'external_model_calls':0,'blocked_network_attempts':len(network_attempts),
        'frozen_inputs':len(frozen['content_sha256']),'changed_frozen_inputs':changed,'artifact_sha256':artifacts,
        'automatic_additional_batches':False,'full_cases_completed':9,'gate_E':'OPEN','gate_F':'OPEN',
        'limitations':['Projection cannot detect forbidden meaning already admitted inside a permitted field; A2 remains DENIED.',
            'Top-level field projection is opt-in; production persistence and restored formal-proof indexes are not implemented.',
            'Local scripted downstream Evidence tests and mechanical Policy parameter checks are not real E1/X5 semantic validation.']}
    write(directory/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='artifact_sha256'},ensure_ascii=False,indent=2))
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
