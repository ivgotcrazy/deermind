"""Offline reconstruction of failed requests using immutable recorded returns.

No network transport is reachable. Generated execution-reference identities may
change; every sent message must otherwise match the actual request exactly.
"""
import json
from pathlib import Path
import tempfile
from collections import Counter

from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter, LLMConfig
from foundation.single_task import ROOT, load_plan, run_batch
from run_single_task_prototype import RUN, verify, write, hashed

OUTPUT = ROOT / 'src/spike/reports/single-task-prototype-offline-analysis-20261007.json'


def normalized(value):
    if isinstance(value, dict):
        if set(value) == {'space', 'identity', 'revision'} and value['space'] == 'execution':
            return {**value, 'identity': '<generated-execution-reference>'}
        return {k: normalized(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    return value


def main():
    verify()
    actual = json.loads((RUN / 'adapter-records.json').read_text(encoding='utf-8'))
    original_result = json.loads((RUN / 'results.json').read_text(encoding='utf-8'))
    state = {}
    oversized, matched = [], []

    def transport(url, key, wire, timeout):
        # Reuse exactly the recorded public response fields, never issue HTTP.
        record = actual[adapter.calls - 1]
        return {'choices': [{'finish_reason': record['finish_reason'], 'message': {
            'content': record['content'], 'tool_calls': record.get('tool_calls')}}]}

    class ReplayAdapter(DeepSeekAdapter):
        def complete(self, messages, purpose, *, output_contract=None):
            length = len(json.dumps(messages, ensure_ascii=False))
            if length > 16000:
                body = json.loads(messages[1]['content'])
                oversized.append({**state, 'purpose': purpose, 'reconstructed_message_chars': length,
                    'limit': 16000, 'system_prompt_chars': len(messages[0]['content']),
                    'body_component_chars': {k: len(json.dumps(v, ensure_ascii=False)) for k, v in body.items()}})
            else:
                expected = actual[self.calls]
                assert purpose == expected['purpose']
                assert output_contract == expected.get('output_contract')
                assert messages[0] == expected['messages'][0]
                assert normalized(json.loads(messages[1]['content'])) == normalized(
                    json.loads(expected['messages'][1]['content']))
                assert length == len(json.dumps(expected['messages'], ensure_ascii=False))
                matched.append({**state, 'original_execution_id': expected['execution_id'], 'purpose': purpose})
            return super().complete(messages, purpose, output_contract=output_contract)

    adapter = ReplayAdapter(LLMConfig('OFFLINE-RECORDED-RETURNS',
        base_url='https://api.deepseek.com/beta', max_calls=168, max_output_tokens=4096), transport)

    def before_turn(spec, number):
        state.update(session=spec['id'], turn=number)

    with tempfile.TemporaryDirectory() as directory:
        result = run_batch(load_plan(), adapter,
            lambda name: EvidenceRecorder(Path(directory) / (name + '.jsonl')), before_turn=before_turn)
    statuses = lambda data: [(r['id'], t['number'], t['execution'], t.get('reason'))
                            for r in data['rows'] for t in r['turns']]
    assert statuses(result) == statuses(original_result)
    assert adapter.calls == len(actual) == len(matched)
    findings = []
    for file in sorted((RUN / 'cases').glob('*.jsonl')):
        events = [json.loads(line) for line in file.read_text(encoding='utf-8').splitlines()]
        for row in (x for x in events if x['kind'] == 'turn_result'):
            calls = [x for x in events if x.get('kind') == 'model_execution' and x['number'] == row['number']]
            last = calls[-1]
            value = json.loads(last['tool_calls'][0]['function']['arguments'])
            problems = []
            if last['purpose'] == 'ArithmeticExtraction':
                for i, segment in enumerate(value['segments']):
                    for j, expr in enumerate(segment['expressions']):
                        if expr['type'] == 'NumericAssertion' and any(expr[k] is None for k in ('operator','left','right','value')):
                            problems.append({'segment': i, 'expression': j, 'issue': 'NumericAssertionHasNullRequiredOperandOrOperator', 'raw': expr})
                        if segment['text'].count(expr['text']) != 1:
                            problems.append({'segment': i, 'expression': j, 'issue': 'ExpressionQuoteNotUniqueWithinOwningSegment',
                                             'quote': expr['text'], 'owning_segment': segment['text']})
            if last['purpose'] == 'ObservationResponsibilityClassification':
                candidate = json.loads(row['work_candidate']['record']['payload_json'])['description']
                cursor = 0
                for i, segment in enumerate(value['segments']):
                    start = candidate.find(segment['text'], cursor)
                    if start < 0 or candidate[cursor:start].strip():
                        problems.append({'segment': i, 'issue': 'CoverageTextNotVerbatimOrLeavesGap',
                                         'returned_text': segment['text'], 'candidate': candidate})
                        break
                    cursor = start + len(segment['text'])
            findings.append({'session': file.stem, 'turn': row['number'], 'runtime_failure': row['reason'],
                             'last_actual_call': last['execution_id'], 'structural_findings': problems})
    report = {'status': 'OFFLINE_RECONSTRUCTION_COMPLETE', 'external_model_calls': 0,
        'reused_recorded_returns': len(actual), 'sent_messages_matched': len(matched),
        'normalization': 'Only generated execution Ref.identity fields; every other sent message value, schema and length must match.',
        'all_24_terminal_outcomes_match': True, 'oversized_unsent_requests': oversized,
        'unsent_lengths_are_reconstructed_not_original_wire_captures': True,
        'failure_counts': dict(Counter(t['reason'] for r in original_result['rows'] for t in r['turns'])),
        'structural_findings': findings, 'semantic_quality_claimed': False,
        'source_sha256': {p.relative_to(ROOT).as_posix(): hashed(p) for p in
                         [Path(__file__), RUN / 'adapter-records.json', RUN / 'results.json']}}
    write(OUTPUT, report)
    print(json.dumps({'status': report['status'], 'matched_messages': len(matched), 'external_model_calls': 0,
        'oversized_requests': len(oversized), 'minimum_chars': min(x['reconstructed_message_chars'] for x in oversized),
        'maximum_chars': max(x['reconstructed_message_chars'] for x in oversized),
        'failure_counts': report['failure_counts']}, indent=2))


if __name__ == '__main__':
    main()
