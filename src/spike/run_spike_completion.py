"""Roadmap-bound completion supplements; independent cases retain independent results."""
import argparse
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from foundation.cases import EvidenceRecorder
from foundation.exit_campaign import ROOT, ExitBudget, execute, audit_messages, read
from foundation.llm import LLMConfig, load_config
from run_network_retry import NetworkRetryAdapter, transport_failure
from run_single_task_prototype import write, hashed, check_hashes
from run_single_task_revision import verify_history

PLAN = ROOT / 'src/spike/fixtures/spike-completion-mechanisms-v1.json'
PACK = ROOT / 'src/spike/review-packages/spike-completion-mechanisms-v1'
RUN = ROOT / 'src/spike/runs/spike-completion-mechanisms-v1'


def mechanics_plan():
    plan = read('src/spike/fixtures/spike-exit-v1.json')
    plan = {k: deepcopy(plan[k]) for k in ('protocols', 'original_fixtures', 'model')}
    old = read('src/spike/fixtures/spike-exit-v1.json')
    plan['schema'] = 'spike-completion-mechanisms-v1'
    plan['schedule'] = [deepcopy(s) for s in old['schedule'] if s['group'] in ('E2', 'F2', 'X1', 'X2')]
    for spec in plan['schedule']:
        spec['logical_max_calls'] = spec['max_calls']
        spec['max_calls'] *= 3
    plan['budget'] = {'max_calls': 60, 'wall_time_seconds': 600, 'transport_retries': 2}
    plan['model'].update(max_output_tokens=2048, max_input_chars=64000)
    plan['purpose'] = 'Complete nine explicitly identified execution gaps; unchanged original fixtures and semantic protocols.'
    plan['semantic_retries'] = 0
    plan['failure_policy'] = 'Preserve each result; ordinary protocol/model failure does not suppress independent cases. Stop on failed deterministic assertions, auth/config failure or exhausted budget.'
    plan['historical_failures_preserved'] = True
    return plan


def batch(plan, adapter, folder, before_case=lambda s: None):
    limited = ExitBudget(adapter, plan['budget'])
    rows, stop = [], None
    for spec in plan['schedule']:
        row = {'id': spec['id'], 'case': spec['group'], 'variant': spec['variant'],
               'historical_gap_repetition': spec['repetition'], 'execution': 'NOT_RUN'}
        if stop is not None:
            row['reason'] = stop
            rows.append(row)
            continue
        start = len(adapter.records)
        adapter.begin_turn(spec['id'], 1)
        before_case(spec)
        limited.begin_case(spec['max_calls'])
        with closing(EvidenceRecorder(folder / 'cases' / (spec['id'] + '.jsonl'))) as evidence:
            try:
                result, _ = execute(evidence, plan, spec, limited)
                row.update(result, execution='COMPLETED')
            except Exception as exc:
                row.update(execution='INCOMPLETE', failure_type=type(exc).__name__, reason=str(exc))
            finally:
                row['checks'] = len(evidence.checks)
                row['failed_checks'] = [c for c in evidence.checks if not c['passed']]
                row['model_calls'] = len(adapter.records) - start
                row['transport_incomplete'] = transport_failure(row.get('reason'))
                for record in adapter.records[start:]:
                    audit_messages(record['messages'])
                    evidence.emit('model_execution', **record)
                evidence.emit('completion_case_result', **row)
        rows.append(row)
        if row['failed_checks']:
            stop = 'DeterministicAssertionFailure:' + spec['id']
        elif row.get('reason') in ('ProviderHTTPError:400', 'ProviderHTTPError:401', 'ProviderHTTPError:403',
                'ProviderHTTPError:404', 'ProviderHTTPError:422', 'WorkingDeadlineExhausted',
                'WorkingDeadlineReachedAfterCall', 'ModelCallBudgetExhausted'):
            stop = row['reason']
        write(folder / 'results.json', {'rows': rows, 'stop_reason': stop})
        print(json.dumps({k: row.get(k) for k in ('id', 'execution', 'coverage', 'result', 'reason', 'model_calls')}, ensure_ascii=True), flush=True)
    result = {'rows': rows, 'stop_reason': stop}
    write(folder / 'results.json', result)
    write(folder / 'adapter-records.json', adapter.records)
    return result


def prepare():
    from prepare_spike_exit import ScriptedTransport
    history = verify_history()
    plan = mechanics_plan()
    if len(plan['schedule']) != 9:
        raise ValueError('UnexpectedGapCount')
    write(PLAN, plan)
    PACK.mkdir(parents=True, exist_ok=False)
    (PACK / 'cases').mkdir()
    transport = ScriptedTransport()
    adapter = NetworkRetryAdapter(LLMConfig('OFFLINE', base_url=plan['model']['provider_endpoint'],
        max_calls=60, max_output_tokens=2048, max_input_chars=64000), transport, sleep=lambda _: None)
    result = batch(plan, adapter, PACK, transport.before_case)
    passed = len(result['rows']) == 9 and all(r.get('result') == 'PASS' for r in result['rows'])
    write(PACK / 'readiness.json', {'status': 'READY' if passed else 'NOT_READY',
        'scripted_cases': len(result['rows']), 'scripted_calls': adapter.calls, 'external_calls': 0,
        'checks': sum(r.get('checks', 0) for r in result['rows']), 'historical_integrity': history})
    paths = list((ROOT / 'src/spike/foundation').glob('*.py')) + [Path(__file__), PLAN,
        ROOT / 'src/spike/run_network_retry.py', ROOT / 'src/spike/prepare_spike_exit.py']
    paths += [ROOT / p for p in set(plan['protocols'].values()) | set(plan['original_fixtures'].values())]
    paths += [ROOT / 'src/spike/reports/remaining-mechanism-review-20261006.json']
    write(PACK / 'manifest.json', {'status': 'READY' if passed else 'NOT_READY', 'plan': plan,
        'source_sha256': {p.relative_to(ROOT).as_posix(): hashed(p) for p in paths},
        'artifact_sha256': {p.relative_to(PACK).as_posix(): hashed(p) for p in PACK.rglob('*') if p.is_file()}})
    if not passed:
        raise ValueError('MechanicalPreparationFailed')
    return {'status': 'READY', 'cases': 9, 'scripted_calls': adapter.calls}


def run():
    frozen = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
    if frozen['status'] != 'READY':
        raise ValueError('PreparationRequired')
    check_hashes(frozen['source_sha256'], ROOT)
    check_hashes(frozen['artifact_sha256'], PACK)
    plan = frozen['plan']
    loaded = load_config(ROOT)
    if not loaded.api_key or loaded.model != plan['model']['model']:
        raise ValueError('ConfiguredModelOrKeyMismatch')
    config = replace(loaded, base_url=plan['model']['provider_endpoint'], max_calls=60,
        max_output_tokens=2048, max_input_chars=64000, timeout_seconds=60)
    RUN.mkdir(parents=True, exist_ok=False)
    (RUN / 'cases').mkdir()
    started = time.monotonic()
    write(RUN / 'manifest.json', {'started_at': datetime.now(timezone.utc).isoformat(),
        'model': config.public(), 'plan': plan, 'source_sha256': frozen['source_sha256'],
        'preparation_sha256': hashed(PACK / 'manifest.json'),
        'authorization': 'User explicitly requested all remaining Spike work with autonomous continuation.'})
    def progress(event):
        if event['event'] == 'attempt_end':
            write(RUN / 'adapter-records.json', adapter.records)
            print(json.dumps(event, ensure_ascii=True), flush=True)
    adapter = NetworkRetryAdapter(config, deadline=started + 600, progress=progress)
    result = batch(plan, adapter, RUN)
    rows = result['rows']
    summary = {'status': 'EXECUTED_EVIDENCE_REVIEW_REQUIRED', 'actual_calls': adapter.calls,
        'elapsed_seconds': round(time.monotonic() - started, 3), 'planned': 9,
        'complete': sum(r.get('coverage') == 'COMPLETE' for r in rows),
        'passed_checks': sum(r.get('checks', 0) - len(r.get('failed_checks', [])) for r in rows),
        'failed_checks': sum(len(r.get('failed_checks', [])) for r in rows),
        'transport_extra_attempts': sum(r['request_attempt'] > 1 for r in adapter.records),
        'transport_incomplete': sum(r.get('transport_incomplete', False) for r in rows),
        'stop_reason': result['stop_reason']}
    write(RUN / 'summary.json', summary)
    write(RUN / 'artifact-sha256.json', {p.relative_to(RUN).as_posix(): hashed(p) for p in RUN.rglob('*') if p.is_file()})
    check_hashes(frozen['source_sha256'], ROOT)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'run'))
    args = parser.parse_args()
    print(json.dumps(prepare() if args.mode == 'prepare' else run(), ensure_ascii=False, indent=2), flush=True)
