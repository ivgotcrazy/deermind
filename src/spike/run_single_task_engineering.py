"""One bounded integration round with fixed protocol revisions and honest failure accounting."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

from foundation.cases import EvidenceRecorder
from foundation.llm import LLMConfig, load_config
from foundation.protocol_preflight import check_observation_contract
from foundation.single_task import ROOT, run_batch
from run_network_retry import NetworkRetryAdapter, transport_failure
from run_single_task_prototype import write, hashed, check_hashes
from run_single_task_revision import verify_history

PLAN = ROOT / 'src/spike/fixtures/single-task-engineering-v1.json'
PACK = ROOT / 'src/spike/review-packages/single-task-engineering-v1'
RUN = ROOT / 'src/spike/runs/single-task-engineering-v1'


def load_plan():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    if (plan['budget'] != {'max_calls': 100, 'wall_time_seconds': 600,
                           'turn_max_calls': 21, 'transport_retries': 2}
            or [s['id'] for s in plan['sessions']] != ['T01', 'T03', 'T05', 'T07', 'T09', 'T12']
            or any(len(s['inputs']) != 2 for s in plan['sessions'])):
        raise ValueError('EngineeringScopeChanged')
    old = json.loads((ROOT / plan['historical_source']).read_text(encoding='utf-8'))
    if any(plan[k] != old[k] for k in ('task', 'actions', 'model')):
        raise ValueError('TaskActionOrModelChanged')
    for spec in plan['sessions']:
        prior = next(s for s in old['sessions'] if s['id'] == spec['id'])
        if any(spec[k] != v for k, v in prior.items()):
            raise ValueError('OriginalCaseChanged')
    definition = json.loads((ROOT / plan['protocols']['work']).read_text(encoding='utf-8'))
    check_observation_contract(definition)
    return plan


def recover_rows(plan, folder, stop):
    rows = []
    for spec in plan['sessions']:
        file = folder / 'cases' / (spec['id'] + '.jsonl')
        events = [json.loads(s) for s in file.read_text(encoding='utf-8').splitlines()] if file.exists() else []
        observed = {e['number']: {k: v for k, v in e.items() if k != 'kind'}
                    for e in events if e['kind'] == 'turn_result'}
        turns = [observed.get(n, {'number': n, 'execution': 'NOT_RUN', 'reason': stop}) for n in (1, 2)]
        rows.append({'id': spec['id'], 'family': spec['family'], 'turns': turns,
                     'execution': 'COMPLETED' if all(t['execution'] == 'COMPLETED' for t in turns) else 'INCOMPLETE'})
    return rows


def summary(result, adapter, elapsed):
    turns = [t for r in result['rows'] for t in r['turns']]
    return {'status': 'EXECUTION_FINISHED_CONTENT_REVIEW_REQUIRED',
        'actual_calls': adapter.calls, 'logical_calls': adapter.logical_calls,
        'transport_extra_attempts': sum(r['request_attempt'] > 1 for r in adapter.records),
        'elapsed_seconds': round(elapsed, 3), 'completed_sessions': sum(r['execution'] == 'COMPLETED' for r in result['rows']),
        'completed_turns': sum(t['execution'] == 'COMPLETED' for t in turns),
        'transport_incomplete_turns': sum(transport_failure(t.get('reason')) for t in turns),
        'nontransport_failed_turns': sum(t['execution'] == 'FAILED' and not transport_failure(t.get('reason')) for t in turns),
        'not_run_turns': sum(t['execution'] == 'NOT_RUN' for t in turns),
        'stop_reason': result['stop_reason'], 'semantic_quality_claimed': False,
        'automatic_followup': False}


def prepare():
    plan = load_plan()
    history = verify_history()
    PACK.mkdir(parents=True, exist_ok=False)
    (PACK / 'cases').mkdir()
    sys.path.insert(0, str(ROOT / 'src/spike/tests'))
    from test_single_task_v2 import IndexedScriptedTransport
    scripted = IndexedScriptedTransport()
    adapter = NetworkRetryAdapter(LLMConfig('OFFLINE', **plan['model'], max_calls=100),
                                   scripted, sleep=lambda _: None)
    stream = io.StringIO()
    with patch('socket.socket.connect', side_effect=RuntimeError('OfflineNetworkForbidden')), \
            patch('socket.create_connection', side_effect=RuntimeError('OfflineNetworkForbidden')):
        tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromNames(['test_feasibility_interfaces', 'test_network_retry']))
        def before(spec, number):
            adapter.begin_turn(spec['id'], number)
            scripted.before_turn(spec, number)
        result = run_batch(plan, adapter, lambda name: EvidenceRecorder(PACK / 'cases' / (name + '.jsonl')),
                           before_turn=before)
    (PACK / 'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
    write(PACK / 'scripted-results.json', result)
    write(PACK / 'scripted-calls.json', adapter.records)
    # Measurement labels never enter provider messages; exact labels are test metadata.
    leaks = []
    for record in adapter.records:
        serialized = json.dumps(record['messages'], ensure_ascii=False)
        for spec in plan['sessions']:
            if spec['author_acceptance'] in serialized:
                leaks.append(record['execution_id'])
        if any('"' + key + '"' in serialized.replace('\\"', '"') for key in
               ('expected_visible_actions', 'scripted_mechanical_outcomes', 'author_acceptance')):
            leaks.append(record['execution_id'])
    passed = tests.wasSuccessful() and result['stop_reason'] is None and not leaks and all(
        r['execution'] == 'COMPLETED' for r in result['rows'])
    readiness = {'status': 'READY' if passed else 'NOT_READY', 'tests': tests.testsRun,
        'scripted_calls': adapter.calls, 'scripted_sessions': len(result['rows']), 'external_calls': 0,
        'label_leaks': leaks, 'semantic_quality_claimed': False, 'historical_integrity': history}
    write(PACK / 'readiness.json', readiness)
    sources = list((ROOT / 'src/spike/foundation').glob('*.py'))
    sources += [PLAN, Path(__file__), ROOT / plan['source_design'], ROOT / plan['historical_source'],
                ROOT / 'src/spike/run_network_retry.py', ROOT / 'src/spike/run_single_task_prototype.py',
                ROOT / 'src/spike/run_single_task_revision.py']
    sources += [ROOT / p for p in plan['protocols'].values()]
    sources += [ROOT / 'src/spike/tests' / (name + '.py') for name in
                ('test_feasibility_interfaces', 'test_network_retry', 'test_single_task', 'test_single_task_v2',
                 'test_indexed_observation', 'test_structured_output')]
    write(PACK / 'manifest.json', {'status': readiness['status'], 'plan': plan,
        'source_sha256': {p.relative_to(ROOT).as_posix(): hashed(p) for p in sources},
        'artifact_sha256': {p.relative_to(PACK).as_posix(): hashed(p) for p in PACK.rglob('*') if p.is_file()}})
    if not passed:
        raise ValueError('EngineeringPreparationFailedSeeSavedArtifacts')
    return readiness


def run():
    manifest = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['status'] != 'READY':
        raise ValueError('EngineeringPreparationRequired')
    check_hashes(manifest['source_sha256'], ROOT)
    check_hashes(manifest['artifact_sha256'], PACK)
    plan = load_plan()
    loaded = load_config(ROOT)
    if not loaded.api_key or loaded.model != plan['model']['model']:
        raise ValueError('ConfiguredModelOrKeyMismatch')
    config = replace(loaded, **plan['model'], max_calls=plan['budget']['max_calls'])
    RUN.mkdir(parents=True, exist_ok=False)
    (RUN / 'cases').mkdir()
    start = time.monotonic()
    write(RUN / 'manifest.json', {'started_at': datetime.now(timezone.utc).isoformat(),
        'source_sha256': manifest['source_sha256'], 'preparation_sha256': hashed(PACK / 'manifest.json'),
        'plan': plan, 'model': {**config.public(), 'retries': 2}, 'max_wall_seconds': 600,
        'semantic_retries': 0, 'authorization': 'User instructed continuation of the restricted engineering stage.'})
    def progress(event):
        if event['event'] == 'attempt_end':
            write(RUN / 'adapter-records.json', adapter.records)
            print(json.dumps(event, ensure_ascii=True), flush=True)
    adapter = NetworkRetryAdapter(config, deadline=start + 600, progress=progress)
    try:
        result = run_batch(plan, adapter, lambda name: EvidenceRecorder(RUN / 'cases' / (name + '.jsonl')),
                           before_turn=lambda spec, number: adapter.begin_turn(spec['id'], number))
    except Exception as exc:
        stop = 'UnexpectedRunnerFailure:' + type(exc).__name__
        result = {'rows': recover_rows(plan, RUN, stop), 'stop_reason': stop, 'calls': adapter.calls}
    write(RUN / 'adapter-records.json', adapter.records)
    write(RUN / 'results.json', result)
    outcome = summary(result, adapter, time.monotonic() - start)
    write(RUN / 'summary.json', outcome)
    write(RUN / 'artifact-sha256.json', {p.relative_to(RUN).as_posix(): hashed(p) for p in RUN.rglob('*') if p.is_file()})
    check_hashes(manifest['source_sha256'], ROOT)
    return outcome


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'run'))
    args = parser.parse_args()
    print(json.dumps(prepare() if args.mode == 'prepare' else run(), ensure_ascii=False, indent=2), flush=True)
