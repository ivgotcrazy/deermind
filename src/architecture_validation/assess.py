"""B5 descriptive metrics and explicit author review; no model calls or runtime fixes."""
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
import statistics
from pathlib import Path
import sqlite3
import zipfile
from .common import BASE,ROOT,digest,write_json,now

RUNS=('b4-primary-v1','b4-continuation-v2')
AUTHOR_SCORES={
 'S1.2':([2,2,2,1],'有依据地区分计算支持与关系解释不足；Policy 将任何提示都说成替代责任，表述偏强。'),
 'S2.1':([2,1,2,2],'提示定位除法且未给商；额外建议乘法验算，略超过只指出步骤的最窄请求。'),
 'S3.1':([2,2,2,1],'保留独立思考、不过度断言能力；不干预理由泛称提示替代计算，表述偏强。'),
 'S4.2':([1,2,0,0],'该会话没有 ActionOccurrence，却把学习者所称提示当成影响表现的真实帮助；Belief 已正式提交。'),
 'S5.1':([2,2,2,1],'正确区分计算表现与未观察到关系解释；Policy 关于任何提示都会替代责任的理由偏强。'),
 'S5.2':([2,2,2,2],'预定 Evaluation 故障如实形成 FAILED，未调用依赖它的 Policy；按故障场景准则评分。'),
 'S6.1':([2,2,2,2],'只有起步请求时保留有依据 UNKNOWN，按请求给方向提示并真实确认展示。')}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def distribution(values):
    values=sorted(values)
    return {'n':len(values),'mean':statistics.mean(values),'median':statistics.median(values),'p95_nearest_rank':values[math.ceil(.95*len(values))-1],'max':max(values)} if values else {'n':0}


def exact_id(row):return row['obj'].split(':',2)[2] if row['version'] else row['obj'] if row['revision'] else row['id']


def reference_diagnostics(rows):
    byid={r['id']:r for r in rows};out=[]
    for failure in rows:
        if failure['kind']!='AttemptFailure' or failure['body']['reason']!='UnknownOrWrongSource':continue
        ctx=byid[failure['body']['context']];provided=ctx['body']['control']['refs'];aliases={}
        for rid in provided:
            for value in (rid,exact_id(byid[rid])):aliases.setdefault(value,set()).add(rid)
        executions=[r for r in rows if r['kind']=='ReasoningExecution' and r['body'].get('context_id')==ctx['id'] and r['body']['role']=='generation']
        values=[]
        def collect(obj):
            if isinstance(obj,dict):
                for k,v in obj.items():
                    if k in ('source_ids','evidence_ids','observation_ids','assistance_ids'):values.extend(v)
                    else:collect(v)
            elif isinstance(obj,list):
                for item in obj:collect(item)
        for execution in executions:collect(execution['body']['output'])
        unknown=[v for v in values if v not in provided]
        out.append({'turn_id':failure['turn_id'],'context_id':ctx['id'],'purpose':failure['body']['purpose'],'attempt':failure['body']['attempt'],
                    'non_record_ids':list(dict.fromkeys(unknown)),'all_non_record_ids_are_explicit_unambiguous_aliases':bool(unknown) and all(len(aliases.get(v,set()))==1 for v in unknown)})
    return out


def main():
    packets=[];reports=[];all_rows=[];byrun={};scored=[]
    for run in RUNS:
        report=read(BASE/'reports'/f'{run}.json');reports.append(report)
        rows=read(BASE/'runs'/run/'records.json');byrun[run]=rows;all_rows+=rows
        for p in read(BASE/'runs'/run/'review-packets.json'):
            p['implementation_version']='v1' if run==RUNS[0] else 'v2';p['run']=run;packets.append(p)
    labels=[p['turn']['label'] for p in packets];assert len(labels)==24 and len(set(labels))==24
    for p in packets:
        label=p['turn']['label'];obs=any(r['kind']=='Observation' for r in p['records']);ev=any(r['kind']=='Evidence' for r in p['records'])
        scores,reason=AUTHOR_SCORES.get(label,([2 if obs else 0,0,1 if ev else 0,0],'未形成完整所需评价和 Policy；已有 Observation/Evidence 单列保留，不以局部输出冒充整轮可用。'))
        if label=='S3.4':scores=[1,0,0,0];reason+=' 来源把未确认的讲解自述写成实际经历。'
        if label=='S4.4':scores=[1,0,1 if ev else 0,0];reason+=' Observation 混用了前题关系说明与本轮新题提交。'
        scored.append({'unit':label,'implementation_version':p['implementation_version'],'scores':scores,'total':sum(scores),'usable':sum(scores)>=6 and 0 not in scores,
            'status':p['turn']['status'],'failure':p['turn']['error'],'review_reason':reason,'supporting_record_ids':[r['id'] for r in p['records'] if r['kind'] in ('Observation','Evidence','Belief','Decision','EvaluationCompletion','RuntimeFailure')],
            'trace':f"runs/{p['run']}/review-packets.json"})
    # The planned fault is an expected terminal branch, not a usable teaching result.
    fault=next(p for p in packets if p['turn']['label']=='S5.2');assert fault['turn']['error']=='InjectedEvaluationFailure'
    assert not any(r['kind']=='Decision' for r in fault['records'])
    assert any(r['kind']=='EvaluationCompletion' and r['body']['execution_status']=='FAILED' for r in fault['records'])
    evaluation=[
      {'dimension':'EVAL-01','result':'INCONCLUSIVE','units':['S1.2','S1.3','S2.2'],'finding':'S1.2 展示不同 Claim 的有限方向性判断与 UNKNOWN；指定 S1.3、S2.2 没有完成 Belief，预定对照不全。'},
      {'dimension':'EVAL-02','result':'NOT SATISFIED','units':['S2.1','S2.2','S3.2','S3.3','S4.1','S4.2','S4.4','S6.3','S6.4'],'finding':'S4.2 无实际帮助记录，却正式写成提示后的重算表现；部分展示与讲解转换未实际发生，其后脚本中的帮助自述不可充当发生事实。'},
      {'dimension':'EVAL-03','result':'INCONCLUSIVE','units':['S1.1','S1.2','S1.4','S2.2','S2.4'],'finding':'S1 更正形成 Observation 修订，但原轮没有成功 Evidence/Belief；后续指定 Belief 未形成，没有真实 Belief 前后修订对照。'},
      {'dimension':'EVAL-04','result':'INCONCLUSIVE','units':['S1.3','S3.2','S5.2','S5.3'],'finding':'预定执行故障准确阻断 Policy；指定有信息/不足对照和故障后恢复均未完整形成。S6.1 合法 UNKNOWN 只列补充证据，不替代缺失对照。'}]
    write_json(BASE/'reports/quality-review-v1.json',{'created':now(),'reviewer':'Implementation author / Codex; not independent blinded human review','rubric_source':'fixtures/holdout-v1.json',
        'unit_reviews':scored,'evaluation':evaluation,'no_semantic_keyword_scoring':True,'g2':'HOLD','cross_version_counts_are_descriptive_only':True})
    call_runs=('b2-real-01','b2-real-02','b2-real-03','b2-real-04')+RUNS
    calls={p.stem:read(p) for run in call_runs for p in (BASE/'runs'/run/'model-calls').glob('attempt_*.json')}
    budget=read(BASE/'reports/api-budget-v1.json');missing={k:v for k,v in budget['reservations'].items() if k not in calls}
    stages=[r['body'] for r in all_rows if r['kind']=='StageTiming'];turns=[p['turn'] for p in packets]
    commits=[r for r in all_rows if r['kind']=='CommitRecord'];effects=[r for r in all_rows if r['kind']=='ActionOccurrence'];transitions=[r for r in all_rows if r['kind']=='ActivityTransitionOccurred']
    versions={}
    for version in ('v1','v2'):
        subset=[s for s in scored if s['implementation_version']==version]
        versions[version]={'planned_executed_turns':len(subset),'completed_normal_turns':sum(s['status']=='COMPLETED' for s in subset),'content_usable_turns':sum(s['usable'] for s in subset),'full_four_turn_sessions':0}
    probes=reports[-1]['probes'];assert len(probes)==12
    byid={r['id']:r for r in all_rows};display_delays=[];queue_delays=[];record_sizes=[]
    for p in packets:
        records=[r for r in byrun[p['run']] if r['turn_id']==p['turn']['id']]
        contexts=[r for r in records if r['kind']=='Context']
        if contexts:queue_delays.append(datetime.fromisoformat(contexts[0]['created']).timestamp()-p['turn']['created'])
        record_sizes.append({'unit':p['turn']['label'],'records':len(records),'serialized_record_bytes':len(json.dumps(records,ensure_ascii=False).encode())})
    for occurrence in effects:
        ds=[r for r in all_rows if r['kind']=='DispatchRecord' and r['body']['dispatch']==occurrence['body']['dispatch']]
        if ds:display_delays.append((datetime.fromisoformat(occurrence['created'])-datetime.fromisoformat(ds[-1]['created'])).total_seconds())
    fanout=[]
    for p in (BASE/'runs/b3-evidence/test_M11_B').glob('records.json'):
        fanout=[r['body'] for r in read(p) if r['kind']=='FanoutMeasurement']
    recovery=[]
    for p in (BASE/'runs/b3-attempt-01').rglob('records.json'):
        rr=read(p);recs=[r for r in rr if r['kind']=='RecoveryRecord']
        for rec in recs:
            earlier=[r for r in rr if r['turn_id']==rec['turn_id'] and r['seq']<rec['seq'] and r['kind'] in ('Candidate','ActionIntent','DispatchRecord')]
            if earlier:recovery.append({'source':str(p.relative_to(BASE)).replace('\\','/'),'last_durable_record_to_recovery_seconds':(datetime.fromisoformat(rec['created'])-datetime.fromisoformat(earlier[-1]['created'])).total_seconds(),'unknown_effect':rec['body']['unknown_effect']})
    diagnostics=[]
    for run,rows in byrun.items():diagnostics += [d|{'run':run} for d in reference_diagnostics(rows)]
    write_json(BASE/'reports/reference-diagnostics-v1.json',{'analysis':'Identity lookup only, no offline semantic repair or replay counted as real success','failures':diagnostics})
    metrics={'created':now(),'g2':'HOLD','versions':versions,'descriptive_only_all_versions':{'turns_executed':24,'completed_normal_turns':sum(t['status']=='COMPLETED' for t in turns),'content_usable_turns':sum(s['usable'] for s in scored),'full_four_turn_sessions':0,'failures':dict(Counter(t['error'] or 'COMPLETED' for t in turns))},
       'probes':{'positive_pass':sum(p['matched'] for p in probes if p['expected']=='PASS'),'positive_planned':6,'negative_rejected':sum(p['matched'] for p in probes if p['expected']=='REJECT'),'negative_planned':6,'false_accepts':[p['id'] for p in probes if p.get('accepted') and p['expected']=='REJECT'],'false_rejects':[p['id'] for p in probes if not p.get('accepted') and p['expected']=='PASS']},
       'budget':{k:v for k,v in budget.items() if k!='reservations'},'captured_http_response_records':len(calls),'missing_attempt_records':missing,
       'captured_input_tokens':sum(c.get('usage',{}).get('prompt_tokens',0) for c in calls.values()),'captured_output_tokens':sum(c.get('usage',{}).get('completion_tokens',0) for c in calls.values()),
       'captured_conservative_CNY':sum((c.get('usage',{}).get('prompt_tokens',0)*2+c.get('usage',{}).get('completion_tokens',0)*8)/1000000 for c in calls.values()),
       'confirmed_transport_failures':sum(c.get('transport_failure',False) for c in calls.values()),
       'B4_active_seconds':sum(s['seconds'] for report in reports for s in report['active_segments']),
       'latency_seconds':{'planned_turn_wall':distribution([t['wall_seconds'] for t in turns]),'HTTP_all_phases':distribution([c['seconds'] for c in calls.values()]),'queue_and_first_context':distribution(queue_delays),'display_dispatch_to_client_ack':distribution(display_delays),
          **{k:distribution([s[k] for s in stages]) for k in ('context_seconds','generation_seconds','review_seconds','commit_seconds')}},
       'model_response_ids':sorted({c['response_model'] for c in calls.values() if c.get('response_model')}),
       'input_admission_max':max(c.get('input_admission_estimate',c.get('input_upper_bound',0)) for c in calls.values()),
       'token_margin_overruns':[c['attempt_id'] for c in calls.values() if c.get('input_admission_estimate') and c['usage']['prompt_tokens']>c['input_admission_estimate']],
       'record_counts':dict(Counter(r['kind'] for r in all_rows)),'record_sizes':record_sizes,
       'databases':{run:{'sqlite_bytes':(BASE/'runs'/run/'runtime.sqlite').stat().st_size,'wal_bytes':(BASE/'runs'/run/'runtime.sqlite-wal').stat().st_size if (BASE/'runs'/run/'runtime.sqlite-wal').exists() else 0} for run in RUNS},
       'actual_display_occurrences':len(effects),'actual_partial_occurrences':sum(r['body']['completeness']=='PARTIAL' for r in effects),'actual_activity_transitions':len(transitions),
       'belief_revisions':dict(Counter(str(r['revision']) for r in all_rows if r['kind']=='Belief')),'fanout':fanout,'recovery_intervals':recovery}
    write_json(BASE/'reports/metrics-v1.json',metrics)
    print(json.dumps({k:metrics[k] for k in ('versions','descriptive_only_all_versions','probes','budget','captured_http_response_records','captured_conservative_CNY','B4_active_seconds')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
