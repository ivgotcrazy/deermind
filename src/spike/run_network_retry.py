"""User-authorized rerun of transport-affected v2 sessions with bounded retries.

The frozen model/prompt/runtime are unchanged. Only transport errors are retried;
all attempts are retained. Sessions restart from turn one to rebuild actual help
history. Old semantic failures are never erased or retried until they pass.
"""
import argparse
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import time
import traceback
import unittest

from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter, ModelFailure, load_config, http_transport
from foundation.single_task import ROOT, run_batch
from run_single_task_prototype import write, hashed, check_hashes
from run_single_task_revision import verify_history

ORIGINAL = ROOT / 'src/spike/runs/single-task-prototype-v2'
PACK = ROOT / 'src/spike/review-packages/single-task-prototype-v2'
ABORTED = ROOT / 'src/spike/runs/single-task-v2-network-retry-v1'
RUN = ROOT / 'src/spike/runs/single-task-v2-network-retry-v2'
MAX_ATTEMPTS = 3
BACKOFF = (2, 5)
RETRYABLE = frozenset(('ProviderTimeout', 'ProviderTLSFailure', 'ProviderDNSFailure',
    'ProviderRemoteDisconnected', 'ProviderConnectionReset', 'ProviderConnectionRefused',
    'ProviderIncompleteRead', 'ProviderNetworkFailure', 'ProviderHTTPError:429',
    'ProviderHTTPError:500', 'ProviderHTTPError:502', 'ProviderHTTPError:503', 'ProviderHTTPError:504'))


def transport_failure(reason):
    return isinstance(reason, str) and reason.removeprefix('ModelFailure:') in RETRYABLE


def select_plan(original_plan, original_result):
    targets = [{'session': r['id'], 'turn': t['number'], 'original_failure': t['reason']}
               for r in original_result['rows'] for t in r['turns']
               if t['execution'] == 'FAILED' and transport_failure(t.get('reason'))]
    affected = {t['session'] for t in targets}
    plan = deepcopy(original_plan)
    plan['sessions'] = [s for s in plan['sessions'] if s['id'] in affected]
    plan['budget'] = {'max_calls': len(plan['sessions']) * 2 * 7 * MAX_ATTEMPTS,
        'wall_time_seconds': 2700, 'turn_max_calls': 7 * MAX_ATTEMPTS,
        'transport_retries': MAX_ATTEMPTS - 1}
    return plan, targets


class NetworkRetryAdapter(DeepSeekAdapter):
    def __init__(self, config, transport=http_transport, *, clock=time.monotonic,
                 sleep=time.sleep, deadline=None, progress=lambda event: None):
        super().__init__(config, transport)
        self.clock, self.sleep, self.deadline = clock, sleep, deadline
        self.progress = progress
        self.logical_calls = 0
        self.turn_logical_calls = 0
        self.state = {}

    def begin_turn(self, session, number):
        self.state = {'session': session, 'turn': number}
        self.turn_logical_calls = 0

    def complete(self, messages, purpose, *, output_contract=None):
        if self.turn_logical_calls >= 7:
            raise ModelFailure('WorkingCallBudgetExhausted')
        self.logical_calls += 1
        self.turn_logical_calls += 1
        original_config = self.config
        # Pin the exact request value once; transport attempts cannot rewrite it.
        messages, output_contract = deepcopy(messages), deepcopy(output_contract)
        try:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                remaining = float('inf') if self.deadline is None else self.deadline - self.clock()
                if remaining <= 0:
                    raise ModelFailure('WorkingDeadlineExhausted')
                if self.calls >= self.config.max_calls:
                    raise ModelFailure('ModelCallBudgetExhausted')
                self.config = replace(original_config, timeout_seconds=min(original_config.timeout_seconds, remaining))
                self.progress({'event': 'attempt_start', **self.state, 'purpose': purpose,
                               'logical_call': self.logical_calls, 'attempt': attempt})
                before = self.calls
                failure = None
                try:
                    return super().complete(messages, purpose, output_contract=output_contract)
                except ModelFailure as exc:
                    failure = str(exc)
                    if failure not in RETRYABLE or attempt == MAX_ATTEMPTS:
                        raise
                finally:
                    if self.calls > before:
                        record = self.records[-1]
                        # run_batch supplies session itself when serializing records.
                        record.update(retry_context=dict(self.state), logical_call=self.logical_calls, request_attempt=attempt,
                                      max_request_attempts=MAX_ATTEMPTS)
                        record['config']['retries'] = MAX_ATTEMPTS - 1
                    self.progress({'event': 'attempt_end', **self.state, 'purpose': purpose,
                        'logical_call': self.logical_calls, 'attempt': attempt, 'actual_calls': self.calls,
                        'status': self.records[-1]['status'] if self.calls > before else 'NOT_SENT',
                        'failure': failure})
                delay = BACKOFF[attempt - 1]
                if self.deadline is not None and self.clock() + delay >= self.deadline:
                    raise ModelFailure('WorkingDeadlineExhausted')
                self.sleep(delay)
        finally:
            self.config = original_config


def verify():
    manifest = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
    check_hashes(manifest['source_sha256'], ROOT)
    check_hashes(manifest['artifact_sha256'], PACK)
    check_hashes(json.loads((ORIGINAL / 'artifact-sha256.json').read_text(encoding='utf-8')), ORIGINAL)
    return manifest


def run():
    frozen = verify()
    history = verify_history()
    original_plan = json.loads((ROOT / 'src/spike/fixtures/single-task-prototype-v2.json').read_text(encoding='utf-8'))
    original_result = json.loads((ORIGINAL / 'results.json').read_text(encoding='utf-8'))
    plan, targets = select_plan(original_plan, original_result)
    if len(targets) != 13 or len(plan['sessions']) != 9:
        raise ValueError('OriginalTransportSelectionChanged')
    check_hashes(json.loads((ABORTED/'artifact-sha256.json').read_text(encoding='utf-8')), ABORTED)
    aborted = json.loads((ABORTED/'summary.json').read_text(encoding='utf-8'))
    if aborted['stop_reason'] != 'UnexpectedRunnerFailure:TypeError':
        raise ValueError('UnexpectedRecoveryBasis')
    # The process lost its in-memory worlds. Restart the selected sessions once,
    # retaining the abort and charging its calls/time against the original cap.
    plan['budget']['max_calls'] -= aborted['actual_model_calls']
    plan['budget']['wall_time_seconds'] -= aborted['elapsed_seconds']
    loaded = load_config(ROOT)
    old_config = json.loads((ORIGINAL / 'manifest.json').read_text(encoding='utf-8'))['public_model_config']
    config = replace(loaded, base_url=old_config['base_url'], max_calls=plan['budget']['max_calls'],
                     max_output_tokens=old_config['max_output_tokens'], timeout_seconds=old_config['timeout_seconds'])
    if not config.api_key or any(config.public()[k] != old_config[k] for k in
                                ('model','base_url','max_output_tokens','timeout_seconds','max_input_chars')):
        raise ValueError('FrozenModelConfigurationChanged')
    sys.path.insert(0, str(ROOT / 'src/spike/tests'))
    suite = unittest.defaultTestLoader.loadTestsFromName('test_network_retry')
    stream = io.StringIO()
    tested = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    if not tested.wasSuccessful():
        print(stream.getvalue())
        raise ValueError('RetryMechanicsTestsFailed')
    RUN.mkdir(parents=True, exist_ok=False)
    (RUN / 'cases').mkdir()
    (RUN / 'unit-tests.txt').write_text(stream.getvalue(), encoding='utf-8')
    started, started_at = time.monotonic(), datetime.now(timezone.utc).isoformat()
    source_hashes = {**frozen['source_sha256'],
        Path(__file__).relative_to(ROOT).as_posix(): hashed(Path(__file__)),
        'src/spike/tests/test_network_retry.py': hashed(ROOT / 'src/spike/tests/test_network_retry.py')}
    write(RUN / 'manifest.json', {'started_at': started_at, 'source_sha256': source_hashes,
        'original_run_sha256': hashed(ORIGINAL / 'artifact-sha256.json'), 'plan': plan, 'network_target_turns': targets,
        'model_config': {**config.public(), 'retries': MAX_ATTEMPTS-1}, 'max_attempts_per_request': MAX_ATTEMPTS,
        'retryable_codes': sorted(RETRYABLE), 'backoff_seconds': list(BACKOFF),
        'network_failures_are_semantic_failures': False, 'historical_failures_erased': False,
        'session_restart_reason': 'Rebuild both turns and actual assistance history coherently; fresh outputs are not the lost original responses.',
        'authorization': 'User requested rerunning transport-failed cases and excluding network faults from semantic conclusions.',
        'retry_tests_passed': tested.testsRun, 'historical_integrity': history})
    recovery = {'aborted_run': ABORTED.relative_to(ROOT).as_posix(),
        'aborted_manifest_sha256': hashed(ABORTED/'manifest.json'),
        'aborted_calls': aborted['actual_model_calls'], 'aborted_seconds': aborted['elapsed_seconds'],
        'reason': 'Duplicate session log keyword crashed the harness after T01/1; only logging metadata changed.',
        'completed_failed_turn_preserved': 'T01/1 ModelFailure:OutputSchemaMismatch',
        'fresh_restart_not_a_replacement_of_prior_failures': True}
    write(RUN/'recovery.json', recovery)
    def progress(event):
        if event['event'] == 'attempt_end':
            write(RUN / 'adapter-records.json', adapter.records)
        print(json.dumps(event, ensure_ascii=True), flush=True)
    adapter = NetworkRetryAdapter(config, deadline=started+plan['budget']['wall_time_seconds'], progress=progress)
    try:
        result = run_batch(plan, adapter, lambda name: EvidenceRecorder(RUN/'cases'/(name+'.jsonl')),
                           before_turn=lambda spec, number: adapter.begin_turn(spec['id'], number))
    except Exception as exc:
        stop = 'UnexpectedRunnerFailure:'+type(exc).__name__
        rows = []
        for spec in plan['sessions']:
            path = RUN/'cases'/(spec['id']+'.jsonl')
            events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []
            observed = {e['number']: {k:v for k,v in e.items() if k!='kind'}
                        for e in events if e['kind']=='turn_result'}
            turns = [observed.get(n, {'number': n, 'execution': 'NOT_RUN', 'reason': stop}) for n in (1,2)]
            rows.append({'id':spec['id'], 'family':spec['family'], 'turns':turns,
                         'execution':'COMPLETED' if all(t['execution']=='COMPLETED' for t in turns) else 'INCOMPLETE'})
        result = {'rows': rows, 'stop_reason': stop, 'calls': adapter.calls}
        write(RUN/'runner-error.json', {'error_type':type(exc).__name__,
            'frames':[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name}
                      for f in traceback.extract_tb(exc.__traceback__)]})
    write(RUN/'adapter-records.json', adapter.records)
    write(RUN/'results.json', result)
    turns = [t for r in result['rows'] for t in r['turns']]
    summary = {'status': 'EXECUTION_FINISHED_REVIEW_REQUIRED', 'started_at': started_at,
        'completed_at': datetime.now(timezone.utc).isoformat(), 'elapsed_seconds': round(time.monotonic()-started,3),
        'actual_model_calls': adapter.calls, 'logical_model_calls': adapter.logical_calls,
        'additional_transport_attempts': sum(r['request_attempt']>1 for r in adapter.records),
        'max_calls': plan['budget']['max_calls'], 'max_wall_seconds': plan['budget']['wall_time_seconds'],
        'completed_sessions': sum(r['execution']=='COMPLETED' for r in result['rows']),
        'completed_turns': sum(t['execution']=='COMPLETED' for t in turns),
        'transport_unresolved_turns': sum(transport_failure(t.get('reason')) for t in turns),
        'nontransport_failed_turns': sum(t['execution']=='FAILED' and not transport_failure(t.get('reason')) for t in turns),
        'not_run_turns': sum(t['execution']=='NOT_RUN' for t in turns), 'stop_reason': result['stop_reason'],
        'network_failures_are_semantic_failures': False, 'automatic_followup_campaign': False}
    write(RUN/'summary.json', summary)
    write(RUN/'artifact-sha256.json', {p.relative_to(RUN).as_posix(): hashed(p) for p in sorted(RUN.rglob('*')) if p.is_file()})
    check_hashes(source_hashes, ROOT)
    verify()
    print(json.dumps(summary, indent=2), flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true',required=True)
    parser.parse_args()
    run()
