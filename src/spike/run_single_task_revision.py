"""One reserved v2 campaign, reusing the v1 serial runner with explicit paths.

No automatic tuning, replacement, transport retry or second campaign is provided.
Historical sources are verified against preserved bytes when a newer revision is
active; manifests and old results are never rewritten to match current sources.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import unittest

from foundation.candidate_spans import registry as candidate_registry
from foundation.cases import EvidenceRecorder
from foundation.expressions import check_expression_extraction_v2
from foundation.llm import DeepSeekAdapter, LLMConfig, load_config
from foundation.protocol_preflight import check_observation_contract
from foundation.single_task import ROOT, run_batch, load_plan as original_plan
import run_single_task_prototype as serial_runner
from run_single_task_prototype import write, hashed

PACK = ROOT / 'src/spike/review-packages/single-task-prototype-v2'
RUN = ROOT / 'src/spike/runs/single-task-prototype-v2'
PLAN = ROOT / 'src/spike/fixtures/single-task-prototype-v2.json'
DESIGN = ROOT / 'doc/system-design/spike/archive/DeerMind_Single_Task_Prototype_Revision_v0.2.md'
BASELINE = ROOT / 'src/spike/reports/source-baseline-single-task-v2-20261007'
WORK = ROOT / 'src/spike/reports/single-task-v2-work-20261007.json'


def load_plan():
    value = json.loads(PLAN.read_text(encoding='utf-8'))
    previous = original_plan()
    for key in ('sessions', 'actions', 'task', 'budget'):
        if value[key] != previous[key]:
            raise ValueError('OriginalAcceptanceChanged:' + key)
    return value


def check_implementation_clock():
    work = json.loads(WORK.read_text(encoding='utf-8'))
    elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(work['observed_start_utc'])).total_seconds()
    elapsed += work['initial_allowance_seconds']
    if elapsed > work['implementation_cap_seconds']:
        raise ValueError('ImplementationTimeBudgetExhausted')
    return elapsed


def verify_history():
    ledger = json.loads((ROOT / 'src/spike/reports/validation-progress-v1.json').read_text(encoding='utf-8'))
    revisions = list(ledger['historical_source_revisions'])
    for old in BASELINE.glob('*.py.txt'):
        revisions.append({'source_path': 'src/spike/foundation/' + old.name[:-4],
                          'previous_sha256': hashed(old), 'preserved_at': old.relative_to(ROOT).as_posix()})
    def verify(name, expected):
        if (ROOT / name).exists() and hashed(ROOT / name) == expected:
            return
        locations = {r['preserved_at'] for r in revisions if r.get('source_path') == name
                     and r.get('previous_sha256') == expected}
        if not locations or not all(hashed(ROOT / path) == expected for path in locations):
            raise ValueError('UnpreservedHistoricalSource:' + name)
    for name, expected in ledger['evidence_sha256'].items():
        verify(name, expected)
    counts = {}
    for name in ('spike-exit-v1', 'policy-s3-diagnostic-v1', 'single-task-prototype-v1', 'input-capacity-v1'):
        base = ROOT / 'src/spike/review-packages' / name
        manifest = json.loads((base / 'manifest.json').read_text(encoding='utf-8'))
        for source, expected in manifest['source_sha256'].items():
            verify(source, expected)
        for artifact, expected in manifest.get('artifact_sha256', {}).items():
            if hashed(base / artifact) != expected:
                raise ValueError('FrozenArtifactChanged:' + artifact)
        counts[name] = len(manifest['source_sha256'])
    return {'ledger_entries_checked': len(ledger['evidence_sha256']), 'frozen_source_counts': counts}


def historical_representation_checks(definition, max_chars):
    """Offline authored representation fixtures, never a runtime response fixer.

    For capacity we deliberately bind each historical mapping to the complete
    candidate. This checks payload size/representability, not semantic fidelity.
    """
    records = json.loads((ROOT / 'src/spike/runs/single-task-prototype-v1/adapter-records.json').read_text(encoding='utf-8'))
    rows, requests, converted = [], [], []
    for record in records:
        if record['purpose'] != 'ArithmeticExtraction':
            continue
        body = json.loads(record['messages'][1]['content'])
        old = json.loads(record['tool_calls'][0]['function']['arguments'])
        entries = candidate_registry(body['candidate'])
        ids = [e['handle'] for e in entries]
        expressions = []
        for segment in old['segments']:
            for item in segment['expressions']:
                current = {k: deepcopy(v) for k, v in item.items() if k != 'text'}
                current['span_ids'] = ids
                if item['type'] == 'NumericAssertion' and item['operator'] is None:
                    assert item['left'] is None and item['right'] is None and item['value'] is not None
                    current['type'] = 'ScalarValue'
                    converted.append({'execution_id': record['execution_id'], 'fixture_type': 'ScalarValue', 'original': item})
                elif item['type'] == 'NumericAssertion' and item['value'] is None:
                    current.update(type='UnevaluatedExpression', stance='not_asserted')
                    converted.append({'execution_id': record['execution_id'], 'fixture_type': 'UnevaluatedExpression', 'original': item})
                expressions.append(current)
        extracted = {'segments': [{'span_ids': ids, 'coverage': 'COMPLETE', 'expressions': expressions}]}
        checked = check_expression_extraction_v2(extracted, body['candidate'], body['source_registry'])
        review_body = {**body, 'candidate_registry': entries, 'criteria': definition['criteria'],
            'arithmetic_fixture': definition.get('arithmetic_fixture', {'42 / 6': 7, '8 * 15': 120, '42 / 6 * 15': 105}),
            'arithmetic_extraction': extracted, 'arithmetic_result': checked}
        messages = [{'role': 'system', 'content': definition['validation_system']},
                    {'role': 'user', 'content': json.dumps(review_body, ensure_ascii=False)}]
        size = len(json.dumps(messages, ensure_ascii=False))
        if size > max_chars:
            raise ValueError('RepresentativeReviewExceedsInputLimit')
        rows.append({'original_execution_id': record['execution_id'], 'candidate_handles': len(entries),
            'expressions': len(expressions), 'message_chars': size, 'arithmetic_status': checked['status']})
        requests.append(messages)
    if len(rows) != 22:
        raise ValueError('HistoricalExtractionFixtureCountChanged')
    return {'external_model_calls': 0, 'source_returns': 22, 'fixture_rows': rows,
            'authored_type_changes': converted, 'semantic_support_claimed': False,
            'maximum_message_chars': max(r['message_chars'] for r in rows),
            'note': 'Whole-candidate handles and explicit test-only type conventions; not replayed model classifications or a production repair path.'}, requests


def prepare():
    if PACK.exists():
        raise ValueError('RevisionPreparationAlreadyReserved')
    check_implementation_clock()
    history, plan = verify_history(), load_plan()
    definition = json.loads((ROOT / plan['protocols']['work']).read_text(encoding='utf-8'))
    check_observation_contract(definition)
    loaded = load_config(ROOT)
    if not loaded.api_key or loaded.model != plan['model']['model'] or loaded.max_input_chars != 64000:
        raise ValueError('ConfiguredModelKeyOrInputLimitMismatch')
    # Run only suites affected by the shared boundary/schema changes, with unique IDs.
    sys.path.insert(0, str(ROOT / 'src/spike/tests'))
    modules = ('test_indexed_observation', 'test_single_task_v2', 'test_single_task',
        'test_expressions', 'test_responsibility', 'test_validation_dimensions', 'test_arithmetic',
        'test_source_handles', 'test_source_review', 'test_absence_review', 'test_claim_axes',
        'test_structured_output', 'test_boundary', 'test_llm', 'test_input_capacity', 'test_policy_v2')
    def flatten(suite):
        for item in suite:
            yield from flatten(item) if isinstance(item, unittest.TestSuite) else (item,)
    tests_by_id = {test.id(): test for name in modules
                   for test in flatten(unittest.defaultTestLoader.loadTestsFromName(name))}
    stream = io.StringIO()
    tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.TestSuite(tests_by_id.values()))
    if not tests.wasSuccessful():
        print(stream.getvalue())
        raise ValueError('RevisionLocalTestsFailed')
    representative, messages = historical_representation_checks(definition, loaded.max_input_chars)
    from test_single_task_v2 import IndexedScriptedTransport
    PACK.mkdir(parents=True, exist_ok=False)
    (PACK / 'cases').mkdir()
    (PACK / 'unit-tests.txt').write_text(stream.getvalue(), encoding='utf-8')
    write(PACK / 'representation-checks.json', representative)
    write(PACK / 'representative-review-messages.json', messages)
    transport = IndexedScriptedTransport()
    adapter = DeepSeekAdapter(LLMConfig('OFFLINE', base_url=plan['model']['base_url'],
        max_calls=168, max_output_tokens=4096, max_input_chars=64000), transport)
    result = run_batch(plan, adapter, lambda name: EvidenceRecorder(PACK / 'cases' / (name + '.jsonl')),
                       before_turn=transport.before_turn)
    write(PACK / 'scripted-results.json', result)
    write(PACK / 'outgoing-requests.json', adapter.records)
    if result['stop_reason'] or any(row['execution'] != 'COMPLETED' for row in result['rows']):
        raise ValueError('RevisionScriptedIntegrationFailed')
    elapsed = check_implementation_clock()
    readiness = {'status': 'MECHANICALLY_READY_CONTENT_UNVERIFIED',
        'completed_at': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'tests_run': tests.testsRun, 'failures': len(tests.failures), 'errors': len(tests.errors),
        'v2_mechanical_tests': 22, 'scripted_sessions': 12, 'scripted_turns': 24, 'scripted_calls': adapter.calls,
        'maximum_scripted_message_chars': max(len(json.dumps(r['messages'], ensure_ascii=False)) for r in adapter.records),
        'representative_historical_message_chars': representative['maximum_message_chars'],
        'implementation_elapsed_seconds': round(elapsed, 3), 'historical_integrity': history,
        'semantic_support_claimed': False}
    write(PACK / 'readiness.json', readiness)
    sources = set((ROOT / 'src/spike/foundation').glob('*.py')) | {
        Path(__file__), Path(serial_runner.__file__), PLAN, DESIGN,
        ROOT / plan['protocols']['work'], ROOT / plan['protocols']['policy'],
        ROOT / 'src/spike/runs/single-task-prototype-v1/adapter-records.json'}
    sources |= {ROOT / 'src/spike/tests' / (name + '.py') for name in modules}
    write(PACK / 'manifest.json', {'status': 'FROZEN_READY', 'configuration_sha256': hashed(PLAN),
        'source_sha256': {p.relative_to(ROOT).as_posix(): hashed(p) for p in sorted(sources)},
        'artifact_sha256': {p.relative_to(PACK).as_posix(): hashed(p) for p in sorted(PACK.rglob('*')) if p.is_file()},
        'max_calls': 168, 'wall_time_seconds': 2700, 'transport_retries': 0, 'replacement_cases': 0,
        'max_input_chars': 64000, 'real_batches_max': 1, 'automatic_followup_campaign': False,
        'authorization': 'User continued the explicit bounded repair and one complete acceptance plan.'})
    work = json.loads(WORK.read_text(encoding='utf-8'))
    work.update(status='FROZEN_READY', implementation_completed_at_utc=readiness['completed_at'],
                implementation_elapsed_seconds=readiness['implementation_elapsed_seconds'])
    write(WORK, work)
    print(json.dumps(readiness, indent=2))


def run():
    # Reuse unchanged execution/evidence/budget code, with explicit versioned inputs.
    serial_runner.PACK, serial_runner.RUN, serial_runner.PLAN = PACK, RUN, PLAN
    serial_runner.DESIGN = DESIGN
    serial_runner.load_plan, serial_runner.verify_history = load_plan, verify_history
    if load_config(ROOT).max_input_chars != 64000:
        raise ValueError('PreparedInputLimitChanged')
    serial_runner.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', action='store_true')
    group.add_argument('--run', action='store_true')
    args = parser.parse_args()
    prepare() if args.prepare else run()
