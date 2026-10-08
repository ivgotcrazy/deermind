"""Offline result extraction plus explicitly authored review; never calls a model."""
import json
from pathlib import Path

from foundation.single_task import ROOT
from run_single_task_prototype import write, hashed, check_hashes

RUN = ROOT / 'src/spike/runs/observer-arithmetic-v1'
PACK = ROOT / 'src/spike/review-packages/observer-arithmetic-v1'
OUT = ROOT / 'src/spike/reports/observer-arithmetic-assessment-20261008.json'

# These are implementation-author judgments after reading raw candidates and
# outputs, not automatic semantic labels inferred by matching natural language.
REVIEW = {
    'T03': {'target_old_defect_absent': True, 'complete_mapping_accepted_by_author': False,
        'notes': '转述、否定和正确商得到区分；完整候选仍因最终结果判断遗漏被拒绝。抽取遗漏任务数值与终端120的独立出现，映射审查未指出；正确商7的陈述还被标为learner。'},
    'T07': {'target_old_defect_absent': True, 'complete_mapping_accepted_by_author': False,
        'notes': '学习者完整连式被保留，未再生成学习者7×15=120的中间断言。观察者自己的7×15=105被独立保留。任务数值未抽取，观察者解释被标为other；原始PASS不等于完整映射无缺陷。'},
    'T09': {'target_old_defect_absent': True, 'complete_mapping_accepted_by_author': False,
        'notes': '报告错误除法不再触发验算拒绝，候选获得综合PASS。任务数值未抽取；观察者对7与105的陈述标为other。保留为映射覆盖与说话人质量问题。'},
    'T12': {'target_old_defect_absent': True, 'complete_mapping_accepted_by_author': False,
        'notes': '报告、否定、正确商及最终结果得到区分，候选获得综合PASS。任务数值仍未抽取，映射审查未指出。'},
    'N01': {'negative_validation_complete': False,
        'notes': '输出segments[0]缺少必需span_ids，schema拒绝；原始内层表达式区分了报告与错误认可，但未进入确定性验算及综合审查。不能记为语义成功拦截。'},
    'N02': {'negative_validation_complete': True, 'deterministic_false_endorsement_check_completed': False,
        'notes': '抽取将明确指代的错误认可降为UnresolvedNumericMapping，未实现预期的算术FAIL。综合审查识别了错误除法与错误最终结果，并判映射FAIL；组合结果UNRESOLVED，未获准入。'},
    'M01': {'injected_mapping_fault_detected': True,
        'notes': '将仅转述注入为AFFIRMS_TRUE，映射审查FAIL，目标错误被发现。grounding理由却把抽取层错误归到原候选，仍有检查维度相互影响；其他维度不作为本例验收目标。'},
    'M02': {'injected_mapping_fault_detected': False,
        'notes': '候选明确认可错误等式，注入仅转述的映射漏掉该认可；审查仍给arithmetic_mapping PASS，理由是认可已在claim中表达。此理由违反当前契约；division/final_result/grounding FAIL最终阻止准入，不能替映射审查记功。'},
}


def analyze():
    manifest = json.loads((PACK / 'manifest.json').read_text(encoding='utf-8'))
    check_hashes(manifest['source_sha256'], ROOT)
    check_hashes(manifest['artifact_sha256'], PACK)
    hashes = json.loads((RUN / 'artifact-sha256.json').read_text(encoding='utf-8'))
    check_hashes(hashes, RUN)
    plan = manifest['plan']
    raw = json.loads((RUN / 'results.json').read_text(encoding='utf-8'))['rows']
    summary = json.loads((RUN / 'summary.json').read_text(encoding='utf-8'))
    records = json.loads((RUN / 'adapter-records.json').read_text(encoding='utf-8'))
    rows = []
    for spec, result in zip(plan['cases'], raw, strict=True):
        assert spec['id'] == result['id']
        criteria = {c['id']: c for c in result.get('review_details', {}).get('criteria', [])}
        checks = result.get('arithmetic', {}).get('result', {}).get('checks', [])
        rows.append({'id': result['id'], 'kind': spec['kind'], 'input': spec['input'],
            'candidate': result['candidate'], 'execution': result['execution'], 'failure': result.get('reason'),
            'actual_calls': result['actual_calls'],
            'raw_arithmetic_status': result.get('arithmetic', {}).get('result', {}).get('status'),
            'raw_mapping_status': criteria.get('arithmetic_mapping', {}).get('status'),
            'raw_combined_status': result.get('review', {}).get('status'),
            'criteria': criteria, 'arithmetic_checks': checks, 'author_review': REVIEW[spec['id']],
            'scripted_fault': result['scripted_injections'],
            'candidate_has_formal_standing': result['candidate_has_formal_standing']})
    historical = rows[:4]
    invalid = next(r for r in records if r['retry_context']['session'] == 'N01' and r['status'] == 'FAILED')
    bad = json.loads(invalid['tool_calls'][0]['function']['arguments'])
    assert 'span_ids' not in bad['segments'][0]
    report = {'schema': 'observer-arithmetic-assessment-v1', 'date': '2026-10-08',
        'status': 'TARGETED_IMPROVEMENT_WITH_REVIEW_LIMITATIONS',
        'scope_closed': True, 'automatic_followup': False, 'production_readiness_established': False,
        'architecture_feasibility_reopened': False, 'run_summary': summary,
        'metrics': {
            'historical_candidates': len(historical),
            'historical_target_defect_absent': sum(r['author_review']['target_old_defect_absent'] for r in historical),
            'historical_raw_arithmetic_pass': sum(r['raw_arithmetic_status'] == 'PASS' for r in historical),
            'historical_raw_combined_pass': sum(r['raw_combined_status'] == 'PASS' for r in historical),
            'authored_negative_cases': 2, 'negative_schema_incomplete': 1,
            'negative_review_nonpass': sum(r['raw_combined_status'] in ('FAIL', 'UNRESOLVED') for r in rows[4:6]),
            'injected_mapping_faults': 2,
            'injected_faults_detected_by_mapping_review': sum(r['author_review']['injected_mapping_fault_detected'] for r in rows[6:]),
            'injected_faults_missed_by_mapping_review': sum(not r['author_review']['injected_mapping_fault_detected'] for r in rows[6:]),
            'formal_commits_tested': 0, 'provider_calls': len(records),
            'provider_schema_failures': sum(r.get('failure') == 'OutputSchemaMismatch' for r in records)},
        'rows': rows,
        'disposition': [
            {'issue': 'Observer commitment confused with reported learner equation; compound equation rewritten as learner intermediate',
             'category': 'TARGETED_IMPLEMENTATION_IMPROVEMENT', 'decision': 'Known four examples improved; retain opt-in protocol. This is not full extraction acceptance.'},
            {'issue': 'Schema response missing segment span_ids', 'category': 'ENGINEERING_OUTPUT_CONTRACT',
             'decision': 'Preserve incomplete result. Later output-shape reliability work; no silent repair or semantic-success credit.'},
            {'issue': 'Implicit endorsement unresolved, missing scalar coverage, speaker attribution and mapping-review miss',
             'category': 'DEFERRED_SEMANTIC_ENGINEERING',
             'decision': 'Retain exact counterexamples. Mapping PASS is not a correctness guarantee. No automatic new tuning batch.'},
            {'issue': 'Final-result omission, responsibility false rejection, direct quote fidelity, Policy rationale quality',
             'category': 'UNCHANGED_ENGINEERING_BACKLOG',
             'decision': 'Next bounded work may address the existing T03 final-result generation omission, not all defects at once.'},
            {'issue': 'Actual hint display followed by learner correction', 'category': 'UNVALIDATED_CAPABILITY',
             'decision': 'Not tested by fixed candidates. Still requires a later bounded integration check; production not ready.'}],
        'reviewer': 'Implementation author; fixed developer examples, one pass, not independent evaluation or an accuracy estimate.',
        'source_sha256': {**{str((RUN / name).relative_to(ROOT).as_posix()): value for name, value in hashes.items()},
            (PACK / 'manifest.json').relative_to(ROOT).as_posix(): hashed(PACK / 'manifest.json'),
            Path(__file__).relative_to(ROOT).as_posix(): hashed(Path(__file__))}}
    write(OUT, report)
    return {k: report[k] for k in ('status', 'scope_closed', 'metrics')}


if __name__ == '__main__':
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
