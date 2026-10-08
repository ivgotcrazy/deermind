"""One frozen fixed-candidate diagnostic; no generation, commit, policy or display."""
import argparse
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

from foundation.candidate_spans import registry
from foundation.cases import EvidenceRecorder
from foundation.llm import load_config
from foundation.protocol_preflight import check_observation_contract
from foundation.records import json_value
from foundation.single_task import ROOT, SingleTaskWorld
from foundation.structured_output import matches_schema
from run_network_retry import NetworkRetryAdapter, transport_failure
from run_single_task_prototype import write, hashed, check_hashes
from run_single_task_revision import verify_history

PLAN = ROOT / 'src/spike/fixtures/observer-arithmetic-v1.json'
PACK = ROOT / 'src/spike/review-packages/observer-arithmetic-v1'
RUN = ROOT / 'src/spike/runs/observer-arithmetic-v1'


class DiagnosticAdapter:
    """Fault injection is explicit test input, never recorded as provider output."""
    def __init__(self, adapter, spec):
        self.adapter, self.spec, self.injections = adapter, spec, []

    @property
    def config(self):
        return self.adapter.config

    def complete(self, messages, purpose, *, output_contract=None):
        if purpose != 'ArithmeticExtraction' or 'injected_observer_position' not in self.spec:
            return self.adapter.complete(messages, purpose, output_contract=output_contract)
        body = json.loads(messages[1]['content'])
        ids = [r['handle'] for r in registry(body['candidate'])]
        # This deliberately authored test mapping is restricted to the two
        # fixed fault cases. Source selection uses the field identity, not text semantics.
        source = next(r['handle'] for r in body['source_registry'] if r['field'] == 'text')
        payload = {'segments': [{'span_ids': ids, 'coverage': 'COMPLETE', 'expressions': [{
            'type': 'ArithmeticEquality', 'span_ids': ids, 'speaker': 'learner', 'sources': [source],
            'observer_position': self.spec['injected_observer_position'],
            'expression_tokens': ['42', '/', '6'], 'value': '8', 'reason': ''}]}]}
        if not matches_schema(payload, output_contract['parameters']):
            raise ValueError('InvalidScriptedFaultShape')
        identity = 'SCRIPTED-MAPPING-FAULT-' + self.spec['id']
        self.injections.append({'identity': identity, 'provider_call': False, 'payload': payload})
        return payload, identity


def load_plan():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    if ([s['id'] for s in plan['cases']] != ['T03', 'T07', 'T09', 'T12', 'N01', 'N02', 'M01', 'M02']
            or plan['budget'] != {'max_calls': 32, 'wall_time_seconds': 600, 'transport_retries': 2}
            or plan['official_commits'] or plan['automatic_followup']):
        raise ValueError('DiagnosticScopeChanged')
    old = json.loads((ROOT / plan['historical_assessment']).read_text(encoding='utf-8'))
    for spec in plan['cases'][:4]:
        row = next(t for t in old['turns'] if t['session'] == spec['id'] and t['turn'] == 1)
        if spec['candidate'] != row['observation'] or spec['input'] != row['input']:
            raise ValueError('HistoricalCandidateChanged')
    check_observation_contract(json.loads((ROOT / plan['protocol']).read_text(encoding='utf-8')))
    return plan


def prepare():
    plan = load_plan()
    history = verify_history()
    sys.path.insert(0, str(ROOT / 'src/spike/tests'))
    stream = io.StringIO()
    names = ['test_observer_arithmetic', 'test_feasibility_interfaces', 'test_indexed_observation',
             'test_observer_diagnostic', 'test_network_retry']
    with patch('socket.socket.connect', side_effect=RuntimeError('OfflineNetworkForbidden')):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromNames(names))
    if not result.wasSuccessful():
        print(stream.getvalue())
        raise ValueError('DiagnosticPreparationFailed')
    PACK.mkdir(parents=True, exist_ok=False)
    (PACK / 'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
    readiness = {'status': 'READY', 'tests': result.testsRun, 'external_calls': 0,
                 'semantic_quality_claimed': False, 'historical_integrity': history}
    write(PACK / 'readiness.json', readiness)
    sources = list((ROOT / 'src/spike/foundation').glob('*.py'))
    sources += [PLAN, Path(__file__), ROOT / plan['source_design'], ROOT / plan['protocol'],
        ROOT / plan['historical_plan'], ROOT / plan['historical_assessment']]
    sources += [ROOT / 'src/spike' / (name + '.py') for name in
                ('run_network_retry', 'run_single_task_prototype', 'run_single_task_revision')]
    sources += [ROOT / 'src/spike/tests' / (name + '.py') for name in names +
                ['test_structured_output', 'test_single_task_v2', 'test_single_task']]
    write(PACK / 'manifest.json', {'status': 'READY', 'plan': plan,
        'source_sha256': {p.relative_to(ROOT).as_posix(): hashed(p) for p in sources},
        'artifact_sha256': {p.relative_to(PACK).as_posix(): hashed(p) for p in PACK.rglob('*') if p.is_file()}})
    return readiness


def run():
    manifest = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['status'] != 'READY':
        raise ValueError('DiagnosticNotPrepared')
    check_hashes(manifest['source_sha256'], ROOT)
    check_hashes(manifest['artifact_sha256'], PACK)
    plan = load_plan()
    loaded = load_config(ROOT)
    if not loaded.api_key or loaded.model != plan['model']['model']:
        raise ValueError('ConfiguredModelOrKeyMismatch')
    config = replace(loaded, **plan['model'], max_calls=plan['budget']['max_calls'])
    base = json.loads((ROOT / plan['historical_plan']).read_text(encoding='utf-8'))
    base['protocols']['work'] = plan['protocol']
    RUN.mkdir(parents=True, exist_ok=False)
    (RUN / 'cases').mkdir()
    start = time.monotonic()
    write(RUN / 'manifest.json', {'started_at': datetime.now(timezone.utc).isoformat(),
        'source_sha256': manifest['source_sha256'], 'preparation_sha256': hashed(PACK / 'manifest.json'),
        'plan': plan, 'model': config.public(), 'semantic_retries': 0, 'official_commits': False,
        'authorization': 'User instructed continuation of the targeted engineering fix.'})
    def progress(event):
        if event['event'] == 'attempt_end':
            write(RUN / 'adapter-records.json', adapter.records)
            print(json.dumps(event, ensure_ascii=True), flush=True)
    adapter = NetworkRetryAdapter(config, deadline=start + plan['budget']['wall_time_seconds'], progress=progress)
    rows = []
    for spec in plan['cases']:
        if adapter.calls >= config.max_calls or time.monotonic() >= adapter.deadline:
            rows.append({'id': spec['id'], 'execution': 'NOT_RUN', 'reason': 'DiagnosticBudgetExhausted'})
            continue
        row = {'id': spec['id'], 'execution': 'COMPLETED', 'candidate': spec['candidate'], 'official_commit': False}
        calls_before = adapter.calls
        adapter.begin_turn(spec['id'], 1)
        proxy = DiagnosticAdapter(adapter, spec)
        with closing(EvidenceRecorder(RUN / 'cases' / (spec['id'] + '.jsonl'))) as evidence:
            world = SingleTaskWorld(evidence, spec['id'], deepcopy(base))
            world.receive(spec['input'])
            world.start()
            ctx = world.context('work')
            candidate = world.runtime.propose(ctx, world.identity('work', 1), 'r1', spec['candidate'])
            try:
                review = world.runtime.validate_with_llm(world.token, candidate, proxy)
                row['review'] = json_value(review)
                row['review_details'] = json.loads(review.details_json)
            except Exception as exc:
                row.update(execution='INCOMPLETE', reason=type(exc).__name__ + ':' + str(exc))
            finally:
                for name, index in [('arithmetic', world.runtime._arithmetic_executions),
                                    ('responsibility', world.runtime._responsibility_executions)]:
                    ref = index.get(candidate.identity)
                    if ref is not None:
                        row[name] = world.h.get(ref).payload
                row['scripted_injections'] = proxy.injections
                row['assessment'] = world.runtime.validation_assessment(candidate)
                row['actual_calls'] = adapter.calls - calls_before
                row['candidate_has_formal_standing'] = world.h.get(candidate.record.ref) is not None
                row['diagnostic_closed'] = world.close_failure('FixedCandidateDiagnosticCompleteNoCommit')
                evidence.emit('diagnostic_result', **row)
                evidence.capture(world.h, 'fixed candidate diagnostic, no commit')
        rows.append(row)
        write(RUN / 'results.json', {'rows': rows})
        print(json.dumps({'case': spec['id'], 'execution': row['execution'],
            'review': row.get('review', {}).get('status'), 'calls': row['actual_calls']}, ensure_ascii=True), flush=True)
    # Only runtime context/candidate data go to the provider, not fixture labels.
    forbidden = ('expected_arithmetic', 'expected_mapping', 'expected_full_review', 'injected_observer_position')
    leaks = [r['execution_id'] for r in adapter.records if any(
        word in json.dumps(r['messages'], ensure_ascii=False) for word in forbidden)]
    summary = {'status': 'EXECUTED_CONTENT_REVIEW_REQUIRED', 'actual_calls': adapter.calls,
        'logical_calls': adapter.logical_calls, 'elapsed_seconds': round(time.monotonic() - start, 3),
        'completed_cases': sum(r['execution'] == 'COMPLETED' for r in rows), 'planned_cases': len(plan['cases']),
        'transport_incomplete': sum(transport_failure(r.get('reason')) for r in rows),
        'transport_extra_attempts': sum(r['request_attempt'] > 1 for r in adapter.records),
        'official_commits': 0, 'label_leaks': leaks, 'automatic_followup': False}
    write(RUN / 'adapter-records.json', adapter.records)
    write(RUN / 'summary.json', summary)
    write(RUN / 'artifact-sha256.json', {p.relative_to(RUN).as_posix(): hashed(p) for p in RUN.rglob('*') if p.is_file()})
    check_hashes(manifest['source_sha256'], ROOT)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'run'))
    args = parser.parse_args()
    print(json.dumps(prepare() if args.mode == 'prepare' else run(), ensure_ascii=False, indent=2), flush=True)
