"""Fixed A1/E1/F2 completion batch; no semantic retry or hidden output repair."""
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
from foundation.formation_cases import run_case as formation
from foundation.policy_cases import run_policy_case
from foundation.protocol_preflight import check_observation_contract
from foundation.llm import LLMConfig, load_config
from prepare_spike_exit import ScriptedTransport
from run_network_retry import NetworkRetryAdapter, transport_failure
from run_single_task_prototype import write, hashed, check_hashes
from run_single_task_revision import verify_history

NAME = 'spike-completion-cognition-v1'
PLAN = ROOT / ('src/spike/fixtures/' + NAME + '.json')
PACK = ROOT / ('src/spike/review-packages/' + NAME)
RUN = ROOT / ('src/spike/runs/' + NAME)


class IndexedTransport(ScriptedTransport):
    """Purely scripted labels for plumbing, never the real model transport."""
    def __call__(self, url, key, wire, timeout):
        response = super().__call__(url, key, wire, timeout)
        function = response['choices'][0]['message']['tool_calls'][0]['function']
        body = json.loads(wire['messages'][1]['content'])
        if not isinstance(body, dict) or 'candidate_registry' not in body:
            return response
        value = json.loads(function['arguments'])
        ids = [r['handle'] for r in body['candidate_registry']]
        if function['name'] in ('submit_responsibility', 'submit_extraction'):
            for segment in value['segments']:
                segment.pop('field')
                segment.pop('text')
                segment['span_ids'] = ids
        elif function['name'] == 'submit_review':
            for criterion in value['criteria']:
                criterion['quotes'] = [{'span_ids': ids}]
            for claim in value['claims']:
                claim.pop('field')
                claim.pop('text')
                claim['span_ids'] = ids
        function['arguments'] = json.dumps(value, ensure_ascii=False)
        return response


def make_plan():
    old = read('src/spike/fixtures/spike-completion-mechanisms-v1.json')
    plan = {k: deepcopy(old[k]) for k in ('protocols', 'original_fixtures', 'model', 'failure_policy')}
    plan.update(schema=NAME, semantic_retries=0, historical_failures_preserved=True,
        purpose='Complete original A1 three-by-five and E1 three-by-five coverage under explicit existing revised contracts; one bounded five-repeat F2 cardinality clarification.')
    plan['protocols'].update(formation_observation='src/spike/protocols/observation-completion-work-v1.json',
        policy='src/spike/protocols/policy-e1-v2.json', security='src/spike/protocols/security-f-completion-v2.json')
    plan['model']['max_output_tokens'] = 4096
    plan['budget'] = {'max_calls': 330, 'wall_time_seconds': 1500, 'transport_retries': 2}
    plan['schedule'] = []
    for group in ('F2', 'A1', 'E1'):
        variants = ([{'id': 'F2-subject-read'}] if group == 'F2' else read(plan['original_fixtures'][group])['variants'])
        for variant in variants:
            for rep in range(1, 6):
                plan['schedule'].append({'id': f'{group}-{variant["id"]}-r{rep}', 'group': group,
                    'variant': variant['id'], 'repetition': rep, 'max_calls': {'F2':3, 'A1':15, 'E1':9}[group]})
    plan['interpretation'] = {
        'A1': 'Review actual committed descriptions against original host expectations; blocked outputs are coverage evidence but not useful Observation successes.',
        'E1': 'LLM utility scores are fallible, test-only and post-dispatch. Author review must examine responsibility/localization and proposed versus occurred help.',
        'F2': 'One declared prompt clarification, unchanged permission scopes; no selecting among multiple tool calls or interpreting invalid output as refusal.',
        'termination': 'All predeclared independent cases attempted unless hard mechanism/config/budget failure. Classify evidence without automatic additional optimization.'}
    return plan


def batch(plan, adapter, folder, before_case=lambda spec: None):
    limited = ExitBudget(adapter, plan['budget'])
    rows, stop = [], None
    for spec in plan['schedule']:
        row = {'id': spec['id'], 'case': spec['group'], 'variant': spec['variant'],
               'repetition': spec['repetition'], 'execution': 'NOT_RUN'}
        if stop:
            row['reason'] = stop
            rows.append(row)
            continue
        start = len(adapter.records)
        adapter.begin_turn(spec['id'], 1)
        limited.begin_case(spec['max_calls'])
        before_case(spec)
        with closing(EvidenceRecorder(folder / 'cases' / (spec['id'] + '.jsonl'))) as e:
            try:
                if spec['group'] == 'A1':
                    fixture = read(plan['original_fixtures']['A1'])
                    variant = next(v for v in fixture['variants'] if v['id'] == spec['variant'])
                    result = formation(e, read(plan['protocols']['formation_observation']), variant, spec['repetition'], limited)
                elif spec['group'] == 'E1':
                    fixture = read(plan['original_fixtures']['E1'])
                    variant = next(v for v in fixture['variants'] if v['id'] == spec['variant'])
                    result = run_policy_case(e, read(plan['protocols']['policy']), fixture, variant, spec['repetition'], limited, rule_revision='v2')
                else:
                    result, _ = execute(e, plan, spec, limited)
                row.update(result, execution='EXECUTED')
            except Exception as exc:
                row.update(execution='INCOMPLETE', failure_type=type(exc).__name__, reason=str(exc))
            finally:
                row.update(checks=len(e.checks), failed_checks=[c for c in e.checks if not c['passed']],
                    model_calls=len(adapter.records)-start)
                row['transport_incomplete'] = transport_failure(row.get('reason'))
                for record in adapter.records[start:]:
                    audit_messages(record['messages'])
                    e.emit('completion_model_execution', **record)
                e.emit('completion_case_result', **row)
        rows.append(row)
        if row['failed_checks']:
            stop = 'DeterministicAssertionFailure:' + spec['id']
        elif row.get('reason') in ('ProviderHTTPError:400','ProviderHTTPError:401','ProviderHTTPError:403',
                'ProviderHTTPError:404','ProviderHTTPError:422','WorkingDeadlineExhausted',
                'WorkingDeadlineReachedAfterCall','ModelCallBudgetExhausted'):
            stop = row['reason']
        write(folder / 'results.json', {'rows': rows, 'stop_reason': stop})
        print(json.dumps({k:row.get(k) for k in ('id','execution','result','semantic_status','commit_status','reason','model_calls')}, ensure_ascii=True), flush=True)
    write(folder / 'adapter-records.json', adapter.records)
    return {'rows':rows, 'stop_reason':stop}


def prepare():
    plan = make_plan()
    protocol = read(plan['protocols']['formation_observation'])
    check_observation_contract(protocol)
    history = verify_history()
    PACK.mkdir(parents=True, exist_ok=False)
    (PACK / 'cases').mkdir()
    write(PLAN, plan)
    transport = IndexedTransport()
    adapter = NetworkRetryAdapter(LLMConfig('OFFLINE', base_url=plan['model']['provider_endpoint'],
        max_calls=330, max_output_tokens=4096, max_input_chars=64000), transport, sleep=lambda _:None)
    result = batch(plan, adapter, PACK, transport.before_case)
    passed = len(result['rows']) == 35 and all(r.get('result') == 'PASS' for r in result['rows'])
    paths = list((ROOT / 'src/spike/foundation').glob('*.py')) + [Path(__file__), PLAN,
        ROOT/'src/spike/run_network_retry.py', ROOT/'src/spike/prepare_spike_exit.py']
    paths += [ROOT/p for p in set(plan['protocols'].values()) | set(plan['original_fixtures'].values())]
    readiness = {'status':'READY' if passed else 'NOT_READY', 'scripted_cases':len(result['rows']),
        'scripted_calls':adapter.calls, 'external_calls':0, 'historical_integrity':history}
    write(PACK/'readiness.json',readiness)
    write(PACK/'manifest.json', {**readiness, 'plan':plan,
        'source_sha256':{p.relative_to(ROOT).as_posix():hashed(p) for p in paths},
        'artifact_sha256':{p.relative_to(PACK).as_posix():hashed(p) for p in PACK.rglob('*') if p.is_file()}})
    if not passed:
        raise ValueError('OfflinePreparationFailed')
    return readiness


def run():
    frozen = json.loads((PACK/'manifest.json').read_text(encoding='utf-8'))
    if frozen['status'] != 'READY':
        raise ValueError('PreparationRequired')
    check_hashes(frozen['source_sha256'], ROOT)
    check_hashes(frozen['artifact_sha256'], PACK)
    plan = frozen['plan']
    loaded = load_config(ROOT)
    if not loaded.api_key or loaded.model != plan['model']['model']:
        raise ValueError('ConfiguredModelOrKeyMismatch')
    config = replace(loaded, base_url=plan['model']['provider_endpoint'], max_calls=330,
        max_output_tokens=4096, max_input_chars=64000, timeout_seconds=60)
    RUN.mkdir(parents=True, exist_ok=False)
    (RUN/'cases').mkdir()
    started = time.monotonic()
    write(RUN/'manifest.json', {'started_at':datetime.now(timezone.utc).isoformat(), 'model':config.public(),
        'plan':plan, 'source_sha256':frozen['source_sha256'], 'preparation_sha256':hashed(PACK/'manifest.json'),
        'authorization':'User authorized all roadmap-bound Spike work and autonomous continuation.'})
    def progress(event):
        if event['event']=='attempt_end':
            write(RUN/'adapter-records.json', adapter.records)
            print(json.dumps(event, ensure_ascii=True), flush=True)
    adapter = NetworkRetryAdapter(config, deadline=started+1500, progress=progress)
    result = batch(plan, adapter, RUN)
    rows = result['rows']
    summary = {'status':'EXECUTED_REVIEW_REQUIRED', 'actual_calls':adapter.calls,
        'elapsed_seconds':round(time.monotonic()-started,3), 'planned':35,
        'executed':sum(r['execution']!='NOT_RUN' for r in rows), 'stop_reason':result['stop_reason'],
        'passed_checks':sum(r.get('checks',0)-len(r.get('failed_checks',[])) for r in rows),
        'failed_checks':sum(len(r.get('failed_checks',[])) for r in rows),
        'transport_extra_attempts':sum(r['request_attempt']>1 for r in adapter.records),
        'transport_incomplete':sum(r.get('transport_incomplete',False) for r in rows)}
    write(RUN/'summary.json', summary)
    write(RUN/'artifact-sha256.json', {p.relative_to(RUN).as_posix():hashed(p) for p in RUN.rglob('*') if p.is_file()})
    check_hashes(frozen['source_sha256'],ROOT)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','run'))
    args=parser.parse_args()
    print(json.dumps(prepare() if args.mode=='prepare' else run(),ensure_ascii=False,indent=2),flush=True)
