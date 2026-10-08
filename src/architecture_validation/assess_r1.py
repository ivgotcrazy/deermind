"""Read-only R1 assessment inputs, explicit author scores, and reproducible accounting."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
import sqlite3
import statistics
from pathlib import Path

from .common import BASE, ROOT, digest, now, write_json

OUT=BASE/'reports/revalidation-r1'
SCORES={
 'r1-dev1':{
  'D1.1':([2,2,2,1],'独立错误计算与请求被记录，Claim 分别评价；不干预理由对转换权限表述偏强。'),
  'D1.2':([2,2,2,2],'真实更正、Evidence 失效和 Belief 修订完成，有限结论与 UNKNOWN 分开。'),
  'D1.3':([2,0,1,0],'Belief 审查误加门槛，未形成完整结果；失效旧 Evidence 未作当前引用。'),
  'D2.1':([2,2,2,1],'允许的一次恢复后实际显示定位提示，未给商；未替代自查的措辞需按保留算商范围理解。'),
  'D2.2':([2,0,2,0],'评价恢复成功，Policy 审查缺少 purpose，恢复配额已用，完整轮次失败。'),
  'D2.3':([2,0,2,0],'实际转换 Teaching，但完整讲解被误拒，没有真实显示。')},
 'r1-dev2':{
  'D1.1':([0,0,0,0],'Observation 被误拒，未提交；零分表示必需结果缺失，不表示候选全部语义错误。'),
  'D1.2':([2,2,2,2],'本轮完整处理正确重算及有限判断；前轮 Observation 缺失，未覆盖原定正式更正目标。'),
  'D1.3':([2,2,2,2],'新写出的单位量解释被当作真实文本表现，单位关系 Belief 从 UNKNOWN 修订为有限 DIRECTIONAL。'),
  'D2.1':([2,2,1,2],'真实显示定位提示并承认帮助；整题 Claim 中识别关系的说法略强，单位关系 Claim 仍为 UNKNOWN，不能据此宣称理解或掌握。'),
  'D2.2':([2,2,2,2],'实际定位帮助后重新评价：整题独立与允许定位支持的除法 Claim 区分，更新 Belief 后完成不干预决策。一次 schema 错误恢复成功。'),
  'D2.3':([2,0,2,0],'真实 Control 已将活动转 Teaching，第二次 Policy 却仍输出 Control，被确定性准入拒绝；缺少请求的讲解展示。')}
}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def distribution(values):
    values=sorted(values)
    return {'n':len(values),'median':statistics.median(values),'p95_nearest_rank':values[math.ceil(len(values)*.95)-1],'max':max(values)} if values else {'n':0}


def main():
    if (OUT/'assessment.json').exists():raise SystemExit('Refusing to overwrite closed assessment')
    summary={'created':now(),'stage':'Development Phase 2 / bounded R1','reviewer':'Implementation author / Codex; no independent blinded human review',
             'formal_campaign_started':False,'formal_turns':0,'formal_probes':0,'gate_G2':'HOLD','runs':{},'errors':[]}
    calls={};reviews=[];all_times=[];all_active=0
    for run in SCORES:
        result=read(OUT/(run+'.json'));rows=read(BASE/'runs'/run/'records.json');packets=read(BASE/'runs'/run/'review-packets.json');byid={r['id']:r for r in rows}
        units=[]
        for packet in packets:
            label=packet['turn']['label'];scores,reason=SCORES[run][label]
            units.append({'unit':label,'scores':scores,'total':sum(scores),'usable':min(scores)>0 and sum(scores)>=6,
                          'review_reason':reason,'status':packet['turn']['status'],'error':packet['turn']['error'],
                          'record_ids':[r['id'] for r in packet['records']],'trace':f'runs/{run}/review-packets.json'})
        reviews.append({'run':run,'units':units})
        exact={}
        for row in rows:
            if digest(row['body'])!=row['hash']:summary['errors'].append('RecordHashMismatch:'+row['id'])
            ident=row['obj'].split(':',2)[2] if row['version'] else row['obj'] if row['revision'] else row['id']
            exact[(row['kind'],ident,row['version'],row['revision'])]=row['hash']
        def verify_ref(value):
            if isinstance(value,dict):
                if set(value)=={'kind','id','version','revision','content_hash'}:
                    key=(value['kind'],value['id'],value['version'],value['revision'])
                    if exact.get(key)!=value['content_hash']:summary['errors'].append('ExactReferenceMismatch:'+str(key))
                for item in value.values():verify_ref(item)
            elif isinstance(value,list):
                for item in value:verify_ref(item)
        for row in rows:verify_ref(row['body'])
        path=(BASE/'runs'/run/'runtime.sqlite').resolve()
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':summary['errors'].append('SQLiteCheckFailed:'+run)
            # Formal current Beliefs cannot depend CURRENT on invalid Evidence.
            bad=db.execute("SELECT count(*) FROM records r JOIN validity v ON v.rid=r.id JOIN heads h ON h.rid=r.id JOIN deps d ON d.child=r.id JOIN records p ON p.id=d.parent JOIN validity pv ON pv.rid=p.id WHERE r.kind='Belief' AND v.valid=1 AND p.kind='Evidence' AND d.mode='CURRENT' AND pv.valid=0").fetchone()[0]
            if bad:summary['errors'].append('InvalidEvidenceInCurrentBelief:'+run)
        expected={'Observation':'Interaction','Decision':'Interaction','Evidence':'Evaluation','Belief':'Evaluation'}
        for row in rows:
            if row['kind'] in expected and row['owner']!=expected[row['kind']]:summary['errors'].append('OwnerMismatch:'+row['id'])
        for p in (BASE/'runs'/run/'model-calls').glob('attempt_*.json'):calls[p.stem]=read(p)
        times=[p['turn']['wall_seconds'] for p in packets];all_times+=times
        active=sum(item['seconds'] for item in result['active_segments']);all_active+=active
        rejected=[r for r in rows if r['kind']=='AttemptFailure']
        deltas=[r for r in rows if r['kind']=='Belief' and r['revision']>1]
        complete=sum(len(s['turns'])==3 and all(t['status']=='COMPLETED' for t in s['turns']) for s in result['sessions'])
        summary['runs'][run]={'planned_turns':6,'normal_completed_turns':sum(p['turn']['status']=='COMPLETED' for p in packets),
             'content_usable_turns':sum(u['usable'] for u in units),'complete_three_turn_sessions':complete,
             'probes':len(result['probes']),'probe_matched':sum(p['matched'] for p in result['probes']),
             'false_accepts':[p['id'] for p in result['probes'] if p['expected']=='REJECT' and p.get('accepted')],
             'actual_displays':sum(r['kind']=='ActionOccurrence' for r in rows),'actual_activity_transitions':sum(r['kind']=='ActivityTransitionOccurred' for r in rows),
             'belief_revisions_after_first':len(deltas),'failures_by_type':dict(Counter(r['body']['reason'] for r in rejected)),
             'model_response_records':sum(c['attempt_id'] in {p.stem for p in (BASE/'runs'/run/'model-calls').glob('attempt_*.json')} for c in calls.values()),
             'active_seconds':active,'turn_seconds':distribution(times),'record_count':len(rows),'source_changes_during_run':result['changed_sources_during_run']}
    budget=read(OUT/'api-budget.json')
    missing=[k for k in budget['reservations'] if k not in calls]
    if missing:summary['errors'].append('MissingResponseRecords')
    ip=sum(c.get('usage',{}).get('prompt_tokens',0) for c in calls.values());op=sum(c.get('usage',{}).get('completion_tokens',0) for c in calls.values())
    if ip!=budget['input_tokens'] or op!=budget['output_tokens']:summary['errors'].append('TokenAccountingMismatch')
    summary['resources']={'http_response_records':len(calls),'reservations':budget['total_attempts'],'missing_response_records':missing,
         'input_tokens':ip,'output_tokens':op,'conservative_cny':(ip*2+op*8)/1_000_000,'transport_failures':sum(bool(c.get('transport_failure')) for c in calls.values()),
         'active_segments_seconds':all_active,'admission_timer_seconds':budget['active_b4_seconds'],
         'timer_difference_explanation':'Segment wall time additionally includes adapter/tokenizer startup before the budget active timer begins; both are disclosed and below cap.',
         'turn_seconds':distribution(all_times),'max_input_admission_estimate':max(c['input_admission_estimate'] for c in calls.values())}
    if len(calls)>460 or ip>4_000_000 or op>1_000_000 or summary['resources']['conservative_cny']>50 or all_active>5400:summary['errors'].append('BudgetExceeded')
    if any(n>80 for n in budget['segment_counts'].values()):summary['errors'].append('DevelopmentSegmentCapExceeded')
    summary['conclusion']='Two development rounds exhausted; readiness not met. No formal G2 retest occurred; retain original HOLD without predicting how unrun heldout samples would perform.'
    write_json(OUT/'quality-review.json',{'created':now(),'reviewer':summary['reviewer'],'runs':reviews,'semantic_keyword_scoring':False})
    write_json(OUT/'admission.json',{'created':now(),'admitted':False,'source':'Build Plan v0.3 section 7.1','complete_sessions_latest':0,'required_complete_sessions':2,
          'reason':'Latest development run completes 4/6 turns and 0/2 whole sessions; known semantic false acceptance remains. Two allowed development rounds used.',
          'new_evidence':['Real hint followed by real Evidence/Belief/Policy on D2.1-D2.2','UNKNOWN to limited DIRECTIONAL update on D1.2-D1.3','Activity transitions actually occur, but explanations do not render.'],
          'next_action':'Close R1. No third development round or formal call without a new bounded decision.'})
    write_json(OUT/'assessment.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if summary['errors']:raise SystemExit(1)


if __name__=='__main__':main()
