"""Prepare or run the single reserved two-turn prototype evaluation."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import time
import unittest

from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter, LLMConfig, load_config
from foundation.single_task import PLAN, ROOT, load_plan, run_batch

PACK = ROOT / 'src/spike/review-packages/single-task-prototype-v1'
RUN = ROOT / 'src/spike/runs/single-task-prototype-v1'
DESIGN = ROOT / 'doc/system-design/spike/archive/DeerMind_Single_Task_Prototype_Revision_and_Acceptance_v0.1.md'


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def hashed(path):
    return sha256(path.read_bytes()).hexdigest()


def check_hashes(mapping, base):
    for name, expected in mapping.items():
        if hashed(base / name) != expected:
            raise ValueError('EvidenceHashMismatch:' + name)


def verify_history():
    ledger = json.loads((ROOT / 'src/spike/reports/validation-progress-v1.json').read_text(encoding='utf-8'))
    check_hashes(ledger['evidence_sha256'], ROOT)
    result = {'ledger_entries_checked': len(ledger['evidence_sha256']), 'frozen_packages': {}}
    for name in ('spike-exit-v1', 'policy-s3-diagnostic-v1'):
        base = ROOT / 'src/spike/review-packages' / name
        manifest = json.loads((base / 'manifest.json').read_text(encoding='utf-8'))
        check_hashes(manifest['source_sha256'], ROOT)
        check_hashes(manifest['artifact_sha256'], base)
        result['frozen_packages'][name] = {'sources': len(manifest['source_sha256']),
                                         'artifacts': len(manifest['artifact_sha256'])}
    return result


def prepare():
    if PACK.exists():
        raise ValueError('PreparationAlreadyReserved')
    history = verify_history()
    plan = load_plan()
    sys.path.insert(0, str(ROOT / 'src/spike/tests'))
    from test_single_task import ScriptedTransport, SingleTaskTests
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SingleTaskTests)
    tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    if not tests.wasSuccessful():
        print(stream.getvalue())
        raise ValueError('MechanicalTestsFailed')
    PACK.mkdir(parents=True, exist_ok=False)
    (PACK / 'cases').mkdir()
    (PACK / 'unit-tests.txt').write_text(stream.getvalue(), encoding='utf-8')
    transport = ScriptedTransport()
    adapter = DeepSeekAdapter(LLMConfig('OFFLINE-ONLY', base_url=plan['model']['base_url'],
        max_calls=168, max_output_tokens=4096), transport)
    result = run_batch(plan, adapter, lambda name: EvidenceRecorder(PACK / 'cases' / (name + '.jsonl')),
                       before_turn=transport.before_turn)
    write(PACK / 'scripted-results.json', result)
    write(PACK / 'outgoing-requests.json', adapter.records)
    if result['stop_reason'] or any(r['execution'] != 'COMPLETED' for r in result['rows']):
        raise ValueError('ScriptedIntegrationFailed')
    test_names = unittest.defaultTestLoader.getTestCaseNames(SingleTaskTests)
    readiness = {'status': 'MECHANICALLY_READY_CONTENT_UNVERIFIED',
        'completed_at': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'tests_run': tests.testsRun, 'failures': len(tests.failures), 'errors': len(tests.errors),
        'matrix': {f'M{i}': {'status': 'PASS', 'tests': [n for n in test_names if n.startswith(f'test_M{i}_')]}
                   for i in range(1, 8)},
        'scripted_sessions': len(result['rows']), 'scripted_turns': sum(len(r['turns']) for r in result['rows']),
        'scripted_calls': adapter.calls,
        'maximum_scripted_message_chars': max(len(json.dumps(r['messages'], ensure_ascii=False)) for r in adapter.records),
        'historical_integrity': history, 'semantic_support_claimed': False,
        'ordinary_failure_continues_independent_samples': True}
    write(PACK / 'readiness.json', readiness)
    sources = sorted(set((ROOT / 'src/spike/foundation').glob('*.py')) |
        {PLAN, Path(__file__), DESIGN, ROOT / 'src/spike/tests/test_single_task.py'} |
        {ROOT / name for name in plan['protocols'].values()})
    write(PACK / 'manifest.json', {'status': 'FROZEN_READY',
        'configuration_sha256': hashed(PLAN),
        'source_sha256': {p.relative_to(ROOT).as_posix(): hashed(p) for p in sources},
        'artifact_sha256': {p.relative_to(PACK).as_posix(): hashed(p)
                           for p in sorted(PACK.rglob('*')) if p.is_file()},
        'max_calls': 168, 'wall_time_seconds': 2700, 'transport_retries': 0,
        'replacement_cases': 0, 'automatic_followup_campaign': False,
        'authorization': 'User requested continuation of the integrated single-task prototype plan.'})
    return readiness


def verify():
    manifest = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
    check_hashes(manifest['source_sha256'], ROOT)
    check_hashes(manifest['artifact_sha256'], PACK)
    if manifest['configuration_sha256'] != hashed(PLAN):
        raise ValueError('ConfigurationChanged')
    return manifest


def run():
    manifest = verify()
    verify_history()
    plan = load_plan()
    loaded = load_config(ROOT)
    if not loaded.api_key or loaded.model != plan['model']['model']:
        raise ValueError('ConfiguredModelOrKeyMismatch')
    model = replace(loaded, base_url=plan['model']['base_url'], max_calls=168,
                    max_output_tokens=4096, timeout_seconds=60)
    RUN.mkdir(parents=True, exist_ok=False)
    (RUN / 'cases').mkdir()
    start = time.monotonic()
    started = datetime.now(timezone.utc).isoformat()
    write(RUN / 'manifest.json', {'started_at': started, 'preparation_sha256': hashed(PACK / 'manifest.json'),
        'source_sha256': manifest['source_sha256'], 'public_model_config': model.public(),
        'attempt': 1, 'retries': 0, 'replacement_cases': 0,
        'authorization': 'User continue after the explicit bounded implementation and evaluation plan.'})
    state = {'session': None, 'turn': None}

    class RecordedAdapter(DeepSeekAdapter):
        def complete(self, messages, purpose, *, output_contract=None):
            print(json.dumps({'event': 'call_start', **state, 'call': self.calls + 1,
                              'purpose': purpose}, ensure_ascii=True), flush=True)
            initial = self.calls
            try:
                return super().complete(messages, purpose, output_contract=output_contract)
            finally:
                write(RUN / 'adapter-records.json', self.records)
                print(json.dumps({'event': 'call_end', **state, 'calls': self.calls,
                    'status': self.records[-1]['status'] if self.calls > initial else 'NOT_SENT'},
                    ensure_ascii=True), flush=True)

    adapter = RecordedAdapter(model)

    def before_turn(spec, number):
        state.update(session=spec['id'], turn=number)
        print(json.dumps({'event': 'turn_start', **state}), flush=True)

    unexpected = None
    try:
        result = run_batch(plan, adapter, lambda name: EvidenceRecorder(RUN / 'cases' / (name + '.jsonl')),
                           before_turn=before_turn)
    except Exception as exc:
        unexpected = type(exc).__name__
        # Preserve captured cases and raw responses. Do not guess missing runtime outcomes.
        result = {'rows': [], 'stop_reason': 'UnexpectedRunnerFailure:' + unexpected,
                  'calls': adapter.calls, 'content_review_required': True}
    write(RUN / 'adapter-records.json', adapter.records)
    write(RUN / 'results.json', result)
    summary = {'status': 'STOPPED_REVIEW_REQUIRED' if result['stop_reason'] else 'EXECUTION_FINISHED_REVIEW_REQUIRED',
        'started_at': started, 'completed_at': datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds': round(time.monotonic() - start, 3), 'actual_model_calls': adapter.calls,
        'maximum_calls': 168, 'maximum_wall_seconds': 2700,
        'completed_sessions': sum(r['execution'] == 'COMPLETED' for r in result['rows']),
        'completed_turns': sum(t['execution'] == 'COMPLETED' for r in result['rows'] for t in r['turns']),
        'failed_turns': sum(t['execution'] == 'FAILED' for r in result['rows'] for t in r['turns']),
        'not_run_turns': sum(t['execution'] == 'NOT_RUN' for r in result['rows'] for t in r['turns']),
        'stop_reason': result['stop_reason'], 'unexpected_failure_type': unexpected,
        'content_review_required': True, 'semantic_support_claimed': False,
        'retries': 0, 'replacement_cases': 0, 'automatic_followup_campaign': False}
    write(RUN / 'summary.json', summary)
    write(RUN / 'artifact-sha256.json', {p.relative_to(RUN).as_posix(): hashed(p)
                                      for p in sorted(RUN.rglob('*')) if p.is_file()})
    verify()
    print(json.dumps(summary, ensure_ascii=True, indent=2), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', action='store_true')
    group.add_argument('--run', action='store_true')
    group.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        print(json.dumps(prepare(), ensure_ascii=True, indent=2))
    elif args.run:
        run()
    else:
        verify()
        configured = load_config(ROOT).public()
        print(json.dumps({'status': 'READY', 'model': configured, 'run_exists': RUN.exists()}, ensure_ascii=True))


if __name__ == '__main__':
    main()
