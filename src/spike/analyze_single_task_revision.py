"""Offline factual inventory for the completed v2 batch; no semantic verdict."""
from collections import Counter
import json
from pathlib import Path

from foundation.candidate_spans import span
from foundation.runtime import ContractError
from foundation.single_task import ROOT
from run_single_task_prototype import hashed, write

RUN = ROOT / 'src/spike/runs/single-task-prototype-v2'
OUT = ROOT / 'src/spike/reports/single-task-v2-execution-analysis-20261007.json'


def main():
    summary = json.loads((RUN / 'summary.json').read_text(encoding='utf-8'))
    result = json.loads((RUN / 'results.json').read_text(encoding='utf-8'))
    adapter = json.loads((RUN / 'adapter-records.json').read_text(encoding='utf-8'))
    context = {}
    for file in sorted((RUN / 'cases').glob('*.jsonl')):
        for line in file.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row['kind'] == 'model_execution':
                context[row['execution_id']] = {'session': file.stem, 'turn': row['number']}
    invalid_spans = []
    for record in adapter:
        if record['status'] != 'COMPLETED' or len(record['messages']) != 2:
            continue
        body = json.loads(record['messages'][1]['content'])
        if not isinstance(body, dict) or 'candidate_registry' not in body:
            continue
        wire = json.loads(record['tool_calls'][0]['function']['arguments'])
        entries = body['candidate_registry']
        def inspect(value, path='$'):
            if isinstance(value, dict):
                if 'span_ids' in value:
                    try:
                        span(value['span_ids'], entries)
                    except ContractError as exc:
                        invalid_spans.append({**context[record['execution_id']],
                            'execution_id': record['execution_id'], 'purpose': record['purpose'],
                            'path': path + '.span_ids', 'handles': value['span_ids'], 'error': str(exc),
                            'selected_original_spans': [r for r in entries if r['handle'] in value['span_ids']]})
                for key, item in value.items():
                    inspect(item, path + '.' + key)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    inspect(item, path + '[' + str(i) + ']')
        inspect(wire)
    turns = [t for r in result['rows'] for t in r['turns']]
    report = {'status': 'OFFLINE_FACTUAL_ANALYSIS_COMPLETE', 'external_model_calls': 0,
        'summary': summary, 'failure_counts': dict(Counter(t.get('reason') for t in turns if t['execution']=='FAILED')),
        'provider_failure_counts': dict(Counter(r.get('failure') for r in adapter if r['status']=='FAILED')),
        'call_purpose_counts': dict(Counter(r['purpose'] for r in adapter)),
        'schema_valid_responses': sum(r['status']=='COMPLETED' for r in adapter),
        'max_sent_message_chars': max(r['input_chars'] for r in adapter),
        'work_commits': sum(t.get('work_commit',{}).get('status')=='Committed' for t in turns),
        'policy_commits': sum(t.get('policy_commit',{}).get('status')=='Committed' for t in turns),
        'settled_turns': sum(t.get('turn_phase')=='SETTLED' for t in turns),
        'displays': [{'session': r['id'], 'turn': t['number'], 'displayed': t['displayed']}
                    for r in result['rows'] for t in r['turns'] if t.get('displayed')],
        'invalid_locator_selections': invalid_spans,
        'semantic_quality_claimed': False,
        'source_sha256': {p.relative_to(ROOT).as_posix(): hashed(p) for p in
            [Path(__file__), RUN/'summary.json', RUN/'results.json', RUN/'adapter-records.json']}}
    write(OUT, report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('summary','invalid_locator_selections','source_sha256')},
                     ensure_ascii=False,indent=2))


if __name__=='__main__':main()
