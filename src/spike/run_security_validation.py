"""One fixed F1/F2 real-model campaign; no retries or replacement batches."""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter, ModelFailure, http_transport, load_config
from foundation.records import json_value
from foundation.runtime import ContractError
from foundation.security import AccessDenied
from foundation.security_cases import SecurityWorld, extra_controls
from run_foundation import manifest
from run_semantic_stability import write_summary

ROOT = Path(__file__).resolve().parent


def load_design():
    fixture = json.loads((ROOT/'fixtures/security-f-v1.json').read_text(encoding='utf-8'))
    if fixture['planned_runs'] != len(fixture['variants']) * fixture['repetitions'] or fixture['max_model_calls'] != fixture['planned_runs']:
        raise ValueError('CampaignBudgetMismatch')
    return fixture, json.loads((ROOT/'protocols/security-f-v1.json').read_text(encoding='utf-8'))


def run_branch(base, e, variant, repetition, config, transport=http_transport):
    row = {'case': variant['case'], 'variant': variant['id'], 'repetition': repetition, 'result': 'NON_SUCCESS',
           'model_result': None, 'injected_result': None, 'coverage': 'INCOMPLETE'}
    adapter = DeepSeekAdapter(config, transport)
    w = base.branch(e)
    e.capture(w.h, 'branch_initial')
    w.prepare(variant)
    # Clone before controls/model so the scripted attack cannot benefit from their result.
    injected = w.branch(e)
    try:
        w.controls()
        if any(not c['passed'] for c in e.checks):
            raise ContractError('PositiveControlInvariantFailed')
        candidate = w.runtime.generate_with_llm(w.token, w.context, adapter, identity='F-model-request')
        e.emit('model_candidate', candidate=json_value(candidate), source_type='REAL-LLM')
        row['model_result'] = w.check_dispatch(candidate, 'real-model')['status']
    except (ModelFailure, ContractError, AccessDenied) as exc:
        row.update(failure_type=type(exc).__name__, reason=str(exc))
    finally:
        for record in adapter.records:
            e.emit('model_execution', variant=variant['id'], repetition=repetition, **record)
        e.capture(w.h, 'model_final')
    injected_candidate = injected.injected(variant['attack'])
    row['injected_result'] = injected.check_dispatch(injected_candidate, 'injected-attack', expected='DENIED')['status']
    e.capture(injected.h, 'injected_final')
    row.update(model_calls=adapter.calls, checks=len(e.checks), failed_checks=[c for c in e.checks if not c['passed']])
    if not row.get('failure_type') and not row['failed_checks']:
        row.update(result='PASS', coverage='COMPLETE')
    e.emit('branch_result', **row)
    return row


def summarize(rows, fixture, stop):
    return {'status': 'PASS' if len(rows) == fixture['planned_runs'] and all(r['result'] == 'PASS' for r in rows) and not stop else 'NON_SUCCESS',
        'planned_runs': fixture['planned_runs'], 'attempted_runs': len(rows), 'not_run': fixture['planned_runs']-len(rows),
        'complete_runs': sum(r['coverage'] == 'COMPLETE' for r in rows), 'model_calls': sum(r['model_calls'] for r in rows),
        'max_model_calls': fixture['max_model_calls'], 'stop_reason': stop, 'runs': rows,
        'assumption_assessment': 'PENDING_EVIDENCE_REVIEW', 'automatic_additional_batches': False, 'gate_E': 'OPEN', 'gate_F': 'OPEN'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args(argv)
    fixture, definition = load_design()
    repo = ROOT.parents[1]
    config = replace(load_config(repo), base_url=definition['provider_endpoint'], max_calls=1,
        max_output_tokens=fixture['max_output_tokens'], timeout_seconds=fixture['timeout_seconds'])
    directory = ROOT/'runs/security-f-v1'
    ready = bool(config.api_key) and not directory.exists()
    if not args.run:
        print(json.dumps({'ready': ready, 'reserved': directory.exists(), 'network_calls': 0,
                          'planned_runs': fixture['planned_runs'], 'model_config': config.public()}, indent=2))
        return 0 if ready else 2
    if not ready:
        print('Not started: missing key or fixed campaign already reserved.')
        return 2
    directory.mkdir(exist_ok=False)
    frozen = manifest(repo)
    design_path = 'src/spike/reports/security-f-design-20261004.md'
    frozen['content_sha256'][design_path] = sha256((repo/design_path).read_bytes()).hexdigest()
    frozen.update(fixture=fixture, model_config=config.public(), cases=['F1', 'F2'], repetitions=5,
                  scope=fixture['scope'], campaign_call_limit=fixture['max_model_calls'])
    (directory/'manifest.json').write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding='utf-8')
    e = EvidenceRecorder(directory/'baseline.jsonl')
    try:
        base = SecurityWorld(e, definition)
        e.capture(base.h, 'shared_initial_snapshot')
    finally: e.close()
    e = EvidenceRecorder(directory/'controls.jsonl')
    try: extra_controls(base, e, fixture['variants'][0])
    finally: e.close()
    rows = []
    stop = 'ControlInvariantFailed' if any(not c['passed'] for c in e.checks) else None
    for repetition in range(1, fixture['repetitions']+1):
        for variant in fixture['variants']:
            if stop: break
            if any(sha256((repo/p).read_bytes()).hexdigest() != h for p, h in frozen['content_sha256'].items()):
                stop = 'FrozenInputsChanged'; break
            e = EvidenceRecorder(directory/f"{repetition}-{variant['id']}.jsonl")
            try: row = run_branch(base, e, variant, repetition, config)
            finally: e.close()
            rows.append(row)
            if row['failed_checks']: stop = 'InvariantCheckFailed'
            elif row.get('reason') in ('ProviderHTTPError:400','ProviderHTTPError:401','ProviderHTTPError:403','ProviderHTTPError:404','ProviderHTTPError:422'):
                stop = row['reason']
            elif len(rows) >= 3 and all(r.get('failure_type') for r in rows[-3:]): stop = 'ConsecutiveProtocolOrRuntimeFailures'
            summary = summarize(rows, fixture, stop)
            write_summary(directory, summary)
            print(json.dumps({k:v for k,v in summary.items() if k != 'runs'}), flush=True)
    summary = summarize(rows, fixture, stop)
    write_summary(directory, summary)
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
