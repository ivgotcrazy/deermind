"""Offline accounting plus explicitly authored content-review notes; never an LLM judge."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json

from foundation.single_task import ROOT
from run_single_task_prototype import hashed, write, check_hashes

RUN = ROOT / 'src/spike/runs/single-task-engineering-v1'
OUT = ROOT / 'src/spike/reports/single-task-engineering-assessment-20261008.json'

# Reviewed against the frozen candidate, original work, request and actual history.
# These judgments are authored by the implementer, not an independent blind reviewer.
REVIEW = {
    ('T01', 1): ('ACCEPTABLE', [], '正确作答与不提示动作一致；未推断稳定掌握。'),
    ('T01', 2): ('EXPLANATION_CONCERN', ['unsupported_help_budget'],
        '不提示动作合理；理由中的 limited help budget 没有对应的来源预算字段，属于依据不清的表述，需工程复核。'),
    ('T03', 1): ('GENERATION_AND_EXTRACTION_DEFECT', ['missing_final_judgment', 'reported_equation_as_endorsed'],
        '候选未明确判断120与原题关系，final_result拒绝有依据；另把转述42÷6=8抽取为asserted_true，叠加一次映射误判。'),
    ('T03', 2): ('EXPLANATION_CONCERN', ['unnecessary_process_speculation'],
        '作答与不提示动作合理；未伪造第一回合帮助。Policy猜测“可能只重读了一次”缺具体依据，留解释质量复核。'),
    ('T05', 1): ('ACCEPTABLE', [], '正确中间步骤与尚无终值区分清楚；等待请求通过NoIntervention满足，无须固定选择Defer。'),
    ('T05', 2): ('ACCEPTABLE', [], '完整作答正确，帮助历史按实际记录处理，未推断稳定掌握。'),
    ('T07', 1): ('EXTRACTION_FALSE_REJECTION', ['reported_equation_as_endorsed', 'invented_intermediate'],
        '候选局部判断合理；抽取为学习者补出中间7并认可7×15=120，既改变了原有陈述，又把转述误作认可。'),
    ('T07', 2): ('ROLE_FALSE_REJECTION', ['local_assistance_uncertainty'],
        '重新计算自述不能证明此前帮助，属于局部来源限度；被误分为evidence_inference，未涉及正式Claim或Evidence权重。'),
    ('T09', 1): ('EXTRACTION_FALSE_REJECTION', ['reported_equation_as_endorsed'],
        '候选已判断错误商和错误终值；转述42÷6=8被抽取为asserted_true后遭验算拒绝。'),
    ('T09', 2): ('QUOTE_CONTRACT_FAILURE', ['nonverbatim_quote'],
        '候选内容合理；review把“7×15＝105，”写成direct_quote，原来源为“7×15＝105；”，精确引用拒绝有依据。'),
    ('T12', 1): ('EXTRACTION_FALSE_REJECTION', ['reported_equation_as_endorsed'],
        '候选明确判断42÷6=8错误、120与105不符；抽取仍把被转述等式标为asserted_true，误拒了观察。'),
    ('T12', 2): ('ACCEPTABLE_WITH_COVERAGE_LIMIT', [],
        '学习者自称得到帮助且独立发现，候选保留其转述归属；实际第一回合失败，系统未将自述变为帮助事实。本轮未覆盖真实提示后的第二回合。'),
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def candidate(turn, role):
    value = turn.get(role + '_candidate')
    return json.loads(value['record']['payload_json']) if value else None


def main():
    check_hashes(read(RUN / 'artifact-sha256.json'), RUN)
    check_hashes(read(RUN / 'manifest.json')['source_sha256'], ROOT)
    plan = read(ROOT / 'src/spike/fixtures/single-task-engineering-v1.json')
    result, records, summary = (read(RUN / name) for name in ('results.json', 'adapter-records.json', 'summary.json'))
    groups = defaultdict(list)
    for record in records:
        groups[(record['retry_context']['session'], record['retry_context']['turn'])].append(record)
    rows = []
    for session in result['rows']:
        spec = next(s for s in plan['sessions'] if s['id'] == session['id'])
        for turn in session['turns']:
            key = (session['id'], turn['number'])
            disposition, tags, note = REVIEW[key]
            role_blocks, arithmetic_blocks, criteria, disjoint = [], [], [], []
            for record in groups[key]:
                if not record.get('tool_calls'):
                    continue
                wire = json.loads(record['tool_calls'][0]['function']['arguments'])
                body = json.loads(record['messages'][1]['content'])
                if record['purpose'] == 'ObservationResponsibilityClassification':
                    role_blocks = [s for s in wire['segments'] if s['role'] not in ('local_observation', 'attributed_report')]
                if record['purpose'] == 'ObservationSemanticValidation':
                    arithmetic_blocks = [c for c in body['arithmetic_result']['checks'] if c['status'] in ('FAIL', 'UNRESOLVED')]
                    criteria = wire['criteria']
                    positions = {x['handle']: i for i, x in enumerate(body['candidate_registry'])}
                    for criterion in criteria:
                        for quote in criterion['quotes']:
                            if any(positions[a]+1 != positions[b] for a, b in zip(quote['span_ids'], quote['span_ids'][1:])):
                                disjoint.append({'criterion': criterion['id'], **quote})
            actual = [next((k for k, v in plan['actions'].items() if v == x['payload']), 'UNREGISTERED')
                      for x in turn.get('displayed', [])]
            expected = spec['expected_visible_actions'][turn['number']-1]
            rows.append({'session': key[0], 'turn': key[1], 'input': spec['inputs'][key[1]-1],
                'execution': turn['execution'], 'reason': turn.get('reason'),
                'observation': candidate(turn, 'work'), 'policy': candidate(turn, 'policy'),
                'work_commit': turn.get('work_commit'), 'policy_commit': turn.get('policy_commit'),
                'role_blocks': role_blocks, 'arithmetic_blocks': arithmetic_blocks, 'raw_criteria': criteria,
                'disjoint_criterion_quotes': disjoint, 'assistance': turn.get('assistance'),
                'actual_visible_actions': actual, 'expected_visible_actions': expected,
                'completed_action_match': actual == expected if turn['execution'] == 'COMPLETED' else None,
                'review_disposition': disposition, 'issue_tags': tags, 'human_review': note})
    assert len(rows) == len(REVIEW) == 12
    metrics = {'completed_sessions': summary['completed_sessions'], 'completed_turns': summary['completed_turns'],
        'provider_or_schema_failures': sum(r['status'] == 'FAILED' for r in records),
        'mandatory_review_rejections': sum(r['reason'] == 'ContractError:workRejected:SemanticValidation:FAIL' for r in rows),
        'quote_contract_failures': sum(r['reason'] == 'ContractError:DirectQuoteNotInCitedSource' for r in rows),
        'observation_commits': sum((r.get('work_commit') or {}).get('status') == 'Committed' for r in rows),
        'policy_commits': sum((r.get('policy_commit') or {}).get('status') == 'Committed' for r in rows),
        'outcomes': dict(Counter(r['policy']['outcome'] for r in rows if r['execution'] == 'COMPLETED')),
        'actual_hint_displays': sum(len(r['actual_visible_actions']) for r in rows),
        'completed_action_matches': sum(r['completed_action_match'] is True for r in rows),
        'committed_policies_citing_execution_context': sum(
            (r.get('policy_commit') or {}).get('status') == 'Committed'
            and any(ref['space'] == 'execution' for ref in r['policy']['context_refs']) for r in rows),
        'disjoint_quote_selections': sum(len(r['disjoint_criterion_quotes']) for r in rows),
        'failure_tags': dict(Counter(tag for r in rows if r['execution'] != 'COMPLETED' for tag in r['issue_tags'])),
        'failure_tags_overlap': True,
        'explanation_review_concerns': sum(r['review_disposition'] == 'EXPLANATION_CONCERN' for r in rows),
        'completed_sessions_without_identified_content_concerns': ['T05'],
        'population_accuracy_estimate': False}
    assert metrics['completed_turns'] == 6 and metrics['observation_commits'] == metrics['policy_commits'] == 6
    started = datetime.fromisoformat(read(RUN / 'manifest.json')['started_at'])
    zone = timezone(timedelta(hours=8))
    sources = [RUN / name for name in ('manifest.json', 'results.json', 'summary.json', 'adapter-records.json', 'artifact-sha256.json')]
    sources += [ROOT / 'src/spike/fixtures/single-task-engineering-v1.json',
                ROOT / 'src/spike/review-packages/single-task-engineering-v1/readiness.json',
                ROOT / 'src/spike/analyze_single_task_engineering.py']
    report = {'schema': 'single-task-engineering-assessment-v1', 'date': '2026-10-08',
        'status': 'ROUND_CLOSED_WITH_ACTIONABLE_FAILURES', 'prototype_status': 'NOT_READY_FOR_LEARNER_USE',
        'architecture_feasibility_reopened': False, 'automatic_new_campaign': False,
        'started_at_china': started.astimezone(zone).isoformat(),
        'approx_ended_at_china': (started + timedelta(seconds=summary['elapsed_seconds'])).astimezone(zone).isoformat(),
        'run_summary': summary, 'metrics': metrics, 'turns': rows,
        'reviewer': 'Implementing assistant, not an independent blind reviewer. Interpretation concerns remain explicit.',
        'next_priority': {'component': 'arithmetic extraction and semantic mapping review',
            'requirement': 'Distinguish observer endorsement from reporting the learner equation. Do not exempt all learner equations or bypass validation.',
            'limits': 'T03/1 also lacks final-result judgment; extraction repair alone is insufficient there. Chained expression must not invent learner intermediate steps.',
            'verification': 'Fixed prepared positive-report and negative-endorsement candidates before another end-to-end batch.'},
        'historical_contract': 'Original 9/17, A2 DENIED and formal gates unchanged.',
        'source_sha256': {p.relative_to(ROOT).as_posix(): hashed(p) for p in sources}}
    write(OUT, report)
    print(json.dumps({'status': report['status'], 'metrics': metrics}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
