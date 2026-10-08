"""Replay 12 previously unsent reviews; test input capacity, not admission.

Preparation reuses all 70 recorded responses with the historical 16K limit.
The real run sends only the 12 reconstructed review requests, once each.
No candidate generation, formal commit, Policy call or effect is performed.
"""
import argparse
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time

from analyze_single_task_prototype import normalized
from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter, LLMConfig, ModelFailure, load_config
from foundation.single_task import ROOT, load_plan, run_batch
from run_single_task_prototype import PACK as ORIGINAL_PACK, RUN as ORIGINAL_RUN, hashed, write

PACK = ROOT / 'src/spike/review-packages/input-capacity-v1'
RUN = ROOT / 'src/spike/runs/input-capacity-v1'
BASELINE = ROOT / 'src/spike/reports/source-baseline-input-capacity-20261007'


def verify_original():
    manifest = json.loads((ORIGINAL_PACK / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['source_sha256'].items():
        path = BASELINE / 'llm.py.txt' if name == 'src/spike/foundation/llm.py' else ROOT / name
        if hashed(path) != expected:
            raise ValueError('HistoricalSourceHashMismatch:' + name)
    for name, expected in manifest['artifact_sha256'].items():
        if hashed(ORIGINAL_PACK / name) != expected:
            raise ValueError('HistoricalArtifactHashMismatch:' + name)
    return manifest


def prepare():
    if PACK.exists():
        raise ValueError('PreparationAlreadyExists')
    original = verify_original()
    actual = json.loads((ORIGINAL_RUN / 'adapter-records.json').read_text(encoding='utf-8'))
    old = json.loads((ORIGINAL_RUN / 'results.json').read_text(encoding='utf-8'))
    state, requests, matched = {}, [], []

    def transport(url, key, wire, timeout):
        record = actual[adapter.calls - 1]
        return {'choices': [{'finish_reason': record['finish_reason'], 'message': {
            'content': record['content'], 'tool_calls': record.get('tool_calls')}}]}

    class ReplayAdapter(DeepSeekAdapter):
        def complete(self, messages, purpose, *, output_contract=None):
            size = len(json.dumps(messages, ensure_ascii=False))
            if size > 16000:
                assert purpose == 'ObservationSemanticValidation'
                requests.append({**state, 'purpose': purpose, 'input_chars': size,
                                 'messages': messages, 'output_contract': output_contract})
            else:
                expected = actual[self.calls]
                assert purpose == expected['purpose']
                assert output_contract == expected.get('output_contract')
                assert messages[0] == expected['messages'][0]
                assert normalized(json.loads(messages[1]['content'])) == normalized(
                    json.loads(expected['messages'][1]['content']))
                assert size == len(json.dumps(expected['messages'], ensure_ascii=False))
                matched.append(expected['execution_id'])
            return super().complete(messages, purpose, output_contract=output_contract)

    adapter = ReplayAdapter(LLMConfig('OFFLINE', base_url='https://api.deepseek.com/beta',
        max_calls=168, max_output_tokens=4096, max_input_chars=16000), transport)
    with tempfile.TemporaryDirectory() as directory:
        replay = run_batch(load_plan(), adapter,
            lambda name: EvidenceRecorder(Path(directory) / (name + '.jsonl')),
            before_turn=lambda spec, number: state.update(session=spec['id'], turn=number))
    outcomes = lambda data: [(r['id'], t['number'], t['execution'], t.get('reason'))
                            for r in data['rows'] for t in r['turns']]
    assert outcomes(replay) == outcomes(old)
    assert len(matched) == adapter.calls == len(actual) == 70
    assert len(requests) == 12

    loaded = load_config(ROOT)
    if loaded.model != 'deepseek-flash':
        raise ValueError('ConfiguredModelMismatch')
    config = replace(loaded, base_url='https://api.deepseek.com/beta',
                     max_calls=12, max_output_tokens=4096, timeout_seconds=60)
    reached = []

    def offline_transport(url, key, wire, timeout):
        reached.append(wire['messages'])
        raise ModelFailure('OfflineTransportReached')

    probe = DeepSeekAdapter(replace(config, api_key='OFFLINE'), offline_transport)
    for request in requests:
        try:
            probe.complete(request['messages'], request['purpose'], output_contract=request['output_contract'])
        except ModelFailure as exc:
            if str(exc) != 'OfflineTransportReached':
                raise
    assert len(reached) == 12 and not probe.input_rejections
    assert reached == [r['messages'] for r in requests]
    PACK.mkdir(parents=True, exist_ok=False)
    write(PACK / 'requests.json', requests)
    sources = {name: hashed(ROOT / name) for name in original['source_sha256']}
    for path in (Path(__file__), ROOT / 'src/spike/analyze_single_task_prototype.py',
                 ROOT / 'src/spike/tests/test_input_capacity.py',
                 ORIGINAL_RUN / 'adapter-records.json', ORIGINAL_RUN / 'results.json'):
        sources[path.relative_to(ROOT).as_posix()] = hashed(path)
    manifest = {'scope': 'Input capacity and provider structured-output diagnostic only; not runtime admission or end-to-end acceptance.',
        'prepared_at': datetime.now(timezone.utc).isoformat(), 'config': config.public(),
        'max_calls': 12, 'wall_time_seconds': 900, 'retries': 0,
        'replayed_responses': 70, 'historical_turn_outcomes_matched': 24,
        'old_limit_blocked': 12, 'new_limit_reaches_mock_transport': len(reached),
        'min_input_chars': min(r['input_chars'] for r in requests),
        'max_input_chars': max(r['input_chars'] for r in requests),
        'historical_normalization': 'Only generated execution Ref.identity fields; all other message values, lengths and output contracts identical.',
        'source_sha256': sources, 'requests_sha256': hashed(PACK / 'requests.json')}
    write(PACK / 'manifest.json', manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k != 'source_sha256'}, indent=2))


def run():
    manifest = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['source_sha256'].items():
        if hashed(ROOT / name) != expected:
            raise ValueError('PreparedSourceChanged:' + name)
    if hashed(PACK / 'requests.json') != manifest['requests_sha256']:
        raise ValueError('PreparedRequestsChanged')
    config = replace(load_config(ROOT), base_url='https://api.deepseek.com/beta',
                     max_calls=12, max_output_tokens=4096, timeout_seconds=60)
    if not config.api_key or config.public() != manifest['config']:
        raise ValueError('PreparedConfigurationChangedOrMissingKey')
    requests = json.loads((PACK / 'requests.json').read_text(encoding='utf-8'))
    adapter = DeepSeekAdapter(config)
    RUN.mkdir(parents=True, exist_ok=False)
    write(RUN / 'manifest.json', {'prepared_manifest_sha256': hashed(PACK / 'manifest.json'),
        'scope': manifest['scope'], 'config': config.public(),
        'started_at': datetime.now(timezone.utc).isoformat()})
    started, rows = time.monotonic(), []
    for request in requests:
        row = {k: request[k] for k in ('session', 'turn', 'purpose', 'input_chars')}
        if time.monotonic() - started >= manifest['wall_time_seconds']:
            row.update(status='NOT_RUN', reason='WallTimeBudgetExhausted')
        else:
            try:
                result, execution = adapter.complete(request['messages'], request['purpose'],
                    output_contract=request['output_contract'])
                row.update(status='COMPLETED', execution_id=execution, result=result)
            except ModelFailure as exc:
                row.update(status='FAILED', reason=str(exc))
        rows.append(row)
        write(RUN / 'adapter-records.json', adapter.records)
        write(RUN / 'results.json', rows)
        print(json.dumps({k: v for k, v in row.items() if k != 'result'}), flush=True)
    summary = {'scope': manifest['scope'], 'completed_at': datetime.now(timezone.utc).isoformat(),
        'calls': adapter.calls, 'elapsed_seconds': round(time.monotonic() - started, 3),
        'provider_status_counts': dict(Counter(r['status'] for r in rows)),
        'input_rejections': adapter.input_rejections,
        'runtime_commits': 0, 'policy_calls': 0, 'effects': 0,
        'end_to_end_acceptance_claimed': False}
    write(RUN / 'summary.json', summary)
    write(RUN / 'artifact-sha256.json', {p.name: hashed(p) for p in sorted(RUN.iterdir()) if p.is_file()})
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    run() if args.run else prepare()
