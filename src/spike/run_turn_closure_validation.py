"""One reserved offline regression run; no API configuration or network transport."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from run_foundation import manifest


ROOT = Path(__file__).resolve().parent


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'runs/turn-closure-v1')
    args = parser.parse_args(argv)
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    repo = ROOT.parents[1]
    frozen = manifest(repo)
    frozen.update(schema='turn-closure-offline-v1', cases=['full-local-unit-suite', 'turn-closure'],
                  scope='Single-process serial failure closure; scripted cognition; synchronous mock effects',
                  model_calls=0, model_config=None, external_network='BLOCKED')
    write_json(directory/'manifest.json', frozen)
    output = io.StringIO()
    network_attempts = []

    def reject_network(*args, **kwargs):
        network_attempts.append('BlockedNetworkAttempt')
        raise RuntimeError('OfflineValidationNetworkDisabled')

    with patch('socket.create_connection', reject_network), patch('socket.socket.connect', reject_network):
        with redirect_stdout(output), redirect_stderr(output):
            suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'))
            closure = sys.modules['test_turn_closure'].TurnClosureTests
            closure.artifact_directory = directory/'cases'
            try:
                result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
            finally:
                closure.artifact_directory = None
    (directory/'unit-tests.txt').write_text(output.getvalue(), encoding='utf-8')
    changed = [p for p, h in frozen['content_sha256'].items()
               if not (repo/p).is_file() or sha256((repo/p).read_bytes()).hexdigest() != h]
    artifacts = {p.relative_to(directory).as_posix(): sha256(p.read_bytes()).hexdigest()
                 for p in sorted(directory.rglob('*')) if p.is_file()}
    summary = {
        'schema': 'turn-closure-offline-result-v1',
        'status': 'PASS' if result.wasSuccessful() and not changed and not network_attempts else 'FAIL',
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'skipped': len(result.skipped), 'closure_evidence_files': len(list((directory/'cases').glob('*.jsonl'))),
        'external_model_calls': 0, 'blocked_network_attempts': len(network_attempts),
        'frozen_inputs': len(frozen['content_sha256']), 'changed_frozen_inputs': changed,
        'artifact_sha256': artifacts, 'full_cases_completed': 9, 'gate_E': 'OPEN', 'gate_F': 'OPEN',
        'automatic_additional_batches': False,
        'limitations': [
            'Scripted cognition is mechanism evidence, not real semantic quality or X5 completion.',
            'Synchronous mock return establishes only local quiescence; remote stop/reconciliation is unimplemented.',
            'Closure is bound by a trusted in-memory coordinator; no crash persistence or distributed transaction claim.',
            'Arithmetic expression types, validation-dimension contracts and authenticated user interruption remain unimplemented.'
        ]}
    write_json(directory/'summary.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'artifact_sha256'}, ensure_ascii=False, indent=2))
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
