"""Offline R2 author assessment and evidence audit; never calls a model."""
from collections import Counter,defaultdict
import hashlib
import json
import sqlite3
import zipfile

from .common import BASE,ROOT,digest,now,write_json
from .assess_r1 import distribution

OUT=BASE/'reports/g2-r2'
RUN=BASE/'runs/g2-r2/v2'
# Scores are explicit author judgments after reading the actual records, not
# keyword classification. Order is the frozen four-dimensional rubric.
SCORES={
 'S1.1':([2,2,2,2],'独立错误作答分别解释为整题/除法反向与关系说明不足；不干预。'),
 'S1.2':([1,2,2,2],'更正形成有效新依据，整题和除法有限支持、关系UNKNOWN；旧乘法“随之不正确”表述不精确。'),
 'S1.3':([2,2,2,2],'新数量意义说明使关系Claim从UNKNOWN变为有限DIRECTIONAL；保留同题相关性。'),
 'S1.4':([2,2,1,2],'新增适用条件自述限制结论，未宣布稳定掌握；将条件识别限制也泛化到除法Claim，范围略宽。'),
 'S2.1':([2,2,2,2],'定位提示实际展示，未给商；理由承认提供定位，提示前评价未倒灌。'),
 'S2.2':([2,2,2,2],'实际定位后的正确商，对整题独立与允许定位支持的除法Claim分别解释。'),
 'S2.3':([2,2,1,1],'新的数量关系说明取得有限支持；提示B2对关系说明的影响论证偏弱，仍未断言独立掌握。'),
 'S2.4':([2,2,1,1],'自述不稳定被用于限制已有结论；关系Claim的支持条件说明与既有支持表述未完全协调。'),
 'S3.1':([2,2,0,0],'把错误商及未说明数量意义误作单位量理解的反证，Evidence与Belief均提交。'),
 'S3.2':([2,2,0,0],'讲解请求与实际讲解区分正确；新关系Evidence为NonInformative，但Belief仍据旧错误维持反向推断。'),
 'S3.3':([2,2,0,0],'正确识别完整答案帮助、未将复现当独立计算；单位量Belief继续引用错误反证。'),
 'S3.4':([1,2,0,0],'单位量错误反证继续传播；整题新Evidence另以帮助前后材料混合为由弱化原始无帮助错误，时序解释不当。'),
 'S4.1':([2,2,0,0],'两块Hint中只有B1实际展示；单位量Claim再次把错误商及缺少解释误作反证。'),
 'S4.2':([2,2,0,0],'只归因实际B1且区分整题/除法责任；单位量Belief仍把旧错误反证与新无信息并用。'),
 'S4.3':([1,2,0,0],'实际B1范围保持；仍引用错误反证，并把“按6份平均分得到一份”说成未说明为何除，低估已有说明。'),
 'S4.4':([1,2,0,0],'保留部分帮助引用但换题影响论证不足；单位量错误反证及对已给平均分理由的误读持续。'),
 'S5.1':([2,2,2,2],'正确算式产生有限支持，单位量说明不足合法UNKNOWN，不干预。'),
 'S5.2':([2,2,2,2],'预定Evidence故障正确形成FAILED且无本轮Decision/成功评价；按异常路径正确性评分，不算自然模型失败。'),
 'S5.3':([2,2,2,2],'故障后新轮真实生成评价，正确纳入新反向表现；未复用旧完成记录。'),
 'S5.4':([2,2,2,1],'修正后正反依据并存，关系仍UNKNOWN；“最终错误、之后改正”的时间措辞冗余。'),
 'S6.1':([2,2,2,1],'纯请求合法UNKNOWN；实际给出数量关系提示，理由“只点名待检查”描述偏轻。'),
 'S6.2':([2,2,2,2],'方法帮助替代关系识别、不替代求商；三项Claim责任分开，除法有限支持。'),
 'S6.3':([2,2,0,0],'明确因提示属于旧题就判新题独立完成，忽略先求单位量的方法迁移，形成不成立的整题支持。'),
 'S6.4':([2,2,0,0],'学习者明确说明沿用旧提示，除法Evidence承认延续，但整题Evidence仍称两题独立、Belief继续使用错误支持。'),
}
EVALUATION={
 'EVAL-01':('SATISFIED','预定S1.2/S1.3/S2.2展示同次表现对不同Claim的不同意义，并限制一次成功的推断。其他场景出现的同类错误仍计入逐轮评分。'),
 'EVAL-02':('NOT SATISFIED','定位/完整讲解/部分展示对照已取得；S6.3按题号变化排除旧方法提示，S6.4明确自述沿用后仍支持整题独立完成，换题对照失败。'),
 'EVAL-03':('SATISFIED','预定S1更正使旧Evidence失效并从当前Belief依据移除；新解释、限制及S2正反材料真实改变依据和理由，非只增revision。'),
 'EVAL-04':('NOT SATISFIED','有信息说明与注入故障/后续恢复已区分；S3.2新Evidence虽认定缺少关系说明不足判断，Belief仍据相同缺失材料保留反向推断，预定不足对照未完整成立。'),
}

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    if (OUT/'assessment.json').exists():raise SystemExit('Closed assessment already exists')
    errors=[];units=[];sessions={};stage=defaultdict(list);all_rows={};times=[]
    for sid in [f'S{i}' for i in range(1,7)]:
        report=read(OUT/'v2'/f'{sid}.json');packets=read(RUN/sid/'review-packets.json');rows=read(RUN/sid/'records.json');all_rows[sid]=rows
        exact={};refs=[0]
        for row in rows:
            ident=row['obj'].split(':',2)[2] if row['version'] else row['obj'] if row['revision'] else row['id']
            exact[(row['kind'],ident,row['version'],row['revision'])]=row['hash']
            if digest(row['body'])!=row['hash']:errors.append('Hash:'+row['id'])
            owner={'Observation':'Interaction','Decision':'Interaction','Evidence':'Evaluation','Belief':'Evaluation'}.get(row['kind'])
            if owner and row['owner']!=owner:errors.append('Owner:'+row['id'])
            if row['kind']=='StageTiming':
                for key in ('context_seconds','generation_seconds','review_seconds','commit_seconds','total_seconds'):stage[key].append(row['body'][key])
        def visit(v):
            if isinstance(v,dict):
                if set(v)=={'kind','id','version','revision','content_hash'}:
                    refs[0]+=1
                    if exact.get((v['kind'],v['id'],v['version'],v['revision']))!=v['content_hash']:errors.append('Reference:'+v['id'])
                for child in v.values():visit(child)
            elif isinstance(v,list):
                for child in v:visit(child)
        for row in rows:visit(row['body'])
        with sqlite3.connect((RUN/sid/'runtime.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
            if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':errors.append('SQLite:'+sid)
            bad=db.execute("SELECT count(*) FROM records r JOIN validity v ON v.rid=r.id JOIN heads h ON h.rid=r.id JOIN deps d ON d.child=r.id JOIN records p ON p.id=d.parent JOIN validity pv ON pv.rid=p.id WHERE r.kind='Belief' AND v.valid=1 AND p.kind='Evidence' AND d.mode='CURRENT' AND pv.valid=0").fetchone()[0]
            if bad:errors.append('InvalidEvidenceInCurrentBelief:'+sid)
        successful=[]
        for packet in packets:
            t=packet['turn'];label=t['label'];score,reason=SCORES[label];times.append(t['wall_seconds'])
            expected=t['injected_fault']=='Evidence' and t['error']=='InjectedEvaluationFailure'
            if expected:
                rs=packet['records']
                expected=not any(r['kind']=='Decision' for r in rs) and any(r['kind']=='EvaluationCompletion' and r['body']['execution_status']=='FAILED' for r in rs)
            successful.append(t['status']=='COMPLETED' or expected)
            units.append({'unit':label,'scores':score,'total':sum(score),'usable':min(score)>0 and sum(score)>=6,'reason':reason,'status':t['status'],'error':t['error'],'expected_fault_handled':expected,'trace':f'runs/g2-r2/v2/{sid}/review-packets.json','record_ids':[r['id'] for r in packet['records'] if r['kind'] in ('Observation','Evidence','Belief','Decision','ActionOccurrence','EvaluationCompletion')]})
        sessions[sid]={'path_completed':len(successful)==4 and all(successful),'normal_completed':sum(p['turn']['status']=='COMPLETED' for p in packets),'planned_faults_handled':sum(u['expected_fault_handled'] for u in units if u['unit'].startswith(sid+'.')),'content_usable':sum(u['usable'] for u in units if u['unit'].startswith(sid+'.')),'wall_seconds':report['wall_seconds'],'records':len(rows),'record_bytes':sum(len(json.dumps(r,ensure_ascii=False).encode()) for r in rows),'database_bytes':(RUN/sid/'runtime.sqlite').stat().st_size,'exact_references_checked':refs[0]}
    calls={};versions={}
    for name,roots in [('v1',[BASE/'runs/g2-r2/S1']),('v2',[RUN/s for s in sessions]+[RUN/'probes'])]:
        current={p.stem:read(p) for root in roots for p in (root/'model-calls').glob('attempt_*.json')};calls.update(current)
        ip=sum(c.get('usage',{}).get('prompt_tokens',0) for c in current.values());op=sum(c.get('usage',{}).get('completion_tokens',0) for c in current.values())
        versions[name]={'attempts':len(current),'logical_requests':len({c['logical_id'] for c in current.values()}),'confirmed_input_tokens':ip,'confirmed_output_tokens':op,'confirmed_usage_cny':(ip*2+op*8)/1e6,'transport_failures':sum(bool(c.get('transport_failure')) for c in current.values()),'normalization_operations':dict(Counter(r['operation'] for c in current.values() for r in c.get('normalization',{}).get('repairs',[])))}
    budget=read(OUT/'api-budget.json');reservations=budget['reservations']
    if set(calls)!=set(reservations):errors.append('AttemptAccountingGap')
    if budget['total_attempts']!=len(calls) or sum(budget['counts'].values())!=len(calls):errors.append('AttemptCountMismatch')
    expected_ip=sum(r.get('actual_input',r['input']) for r in reservations.values());expected_op=sum(r.get('actual_output',r['output']) for r in reservations.values())
    if (expected_ip,expected_op)!=(budget['input_tokens'],budget['output_tokens']):errors.append('TokenAccountingMismatch')
    for name,current in versions.items():
        ids={p.stem for root in ([BASE/'runs/g2-r2/S1'] if name=='v1' else [RUN/s for s in sessions]+[RUN/'probes']) for p in (root/'model-calls').glob('attempt_*.json')}
        current['conservative_cny_including_unconfirmed_attempts']=sum(reservations[i].get('actual_estimated_cny',reservations[i]['cost']) for i in ids)
    groups=defaultdict(list)
    for c in calls.values():groups[c['logical_id']].append(c)
    unrecovered=[key for key,items in groups.items() if any(c.get('transport_failure') for c in items) and not any(c.get('status')=='COMPLETED' for c in items)]
    if unrecovered:errors.append('UnrecoveredTransport')
    frozen=read(OUT/'v2/freeze.json')
    for prefix in ('','v2/'):
        f=read(OUT/(prefix+'freeze.json'))
        with zipfile.ZipFile(OUT/(prefix+'source.zip')) as z:
            for path,h in f['source_sha256'].items():
                if hashlib.sha256(z.read(path)).hexdigest()!=h:errors.append('SourceArchive:'+path)
    probe=read(OUT/'v2/probes.json');items=probe['items']
    positives=[p for p in items if p['expected']=='PASS'];negatives=[p for p in items if p['expected']=='REJECT']
    usable=sum(u['usable'] for u in units);complete=sum(s['path_completed'] for s in sessions.values())
    evaluation={k:{'status':v[0],'reason':v[1],'predeclared_contrast':frozen['spec']['evaluation_contrasts'][k],'record_ids':[rid for u in units if u['unit'] in frozen['spec']['evaluation_contrasts'][k]['turns'] for rid in u['record_ids']]} for k,v in EVALUATION.items()}
    summary={'created':now(),'status':'CLOSED','stage':'Development Phase 2 Architecture Validation Build','gate_G2':'HOLD','scoring_version':'v2 only; v1 retained separately','reviewer':'Implementation author / Codex; not independent blinded human assessment','sessions':sessions,'content_usable':usable,'planned_turns':24,'complete_scenario_paths':complete,'normal_completed_turns':sum(s['normal_completed'] for s in sessions.values()),'expected_fault_paths':sum(s['planned_faults_handled'] for s in sessions.values()),'evaluation':evaluation,'offline_checks':75,'offline_mechanism_paths':24,'probes':{'planned':12,'completed':sum(p['status']=='COMPLETED' for p in items),'matched':sum(p['matched'] for p in items),'false_accepts':[p['id'] for p in negatives if p.get('accepted')],'false_rejects':[p['id'] for p in positives if p.get('output',{}).get('verdict')=='FAIL'],'unresolved':[p['id'] for p in items if p.get('output',{}).get('verdict')=='UNRESOLVED'],'format_failures':[p['id'] for p in items if p['status']=='FAILED'],'positive_denominator':len(positives),'negative_denominator':len(negatives)},'resources':{'versions':versions,'budget':{k:v for k,v in budget.items() if k!='reservations'},'unrecovered_transport_logical_requests':unrecovered,'v2_wall_seconds_including_startup':sum(s['wall_seconds'] for s in sessions.values())+probe['wall_seconds'],'turn_seconds':distribution(times),'normal_turn_seconds':distribution([p['turn']['wall_seconds'] for sid in sessions for p in read(RUN/sid/'review-packets.json') if not p['turn']['injected_fault']]),'stage_seconds':{k:distribution(v) for k,v in stage.items()},'stage_totals':{k:sum(v) for k,v in stage.items()},'max_input_admission_estimate':max(c['input_admission_estimate'] for c in calls.values())},'integrity_errors':errors,'source_verification':read(OUT/'v2/source-verification.json'),'decision':'Mechanism paths run; content quality and two predeclared Evaluation contrasts fail. This configuration does not pass G2; no evidence of an architectural impossibility. No further model calls in R2.'}
    write_json(OUT/'quality-review.json',{'created':now(),'reviewer':summary['reviewer'],'rubric':frozen['spec']['rubric'],'semantic_keyword_scoring':False,'units':units,'propagation_note':'S3/S4 failures include persistent downstream effects of two initial bad unit-relation Evidence items; ten unusable turns are not ten independent root causes.'})
    write_json(OUT/'assessment.json',summary)
    print(json.dumps({'gate':summary['gate_G2'],'usable':usable,'paths':complete,'versions':versions,'integrity_errors':errors},ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
