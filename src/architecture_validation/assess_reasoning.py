"""Offline author assessment of the closed fixed-input R4 comparison."""
from collections import Counter,defaultdict
import hashlib
import json
import math
import statistics
import zipfile

from .common import BASE,ROOT,digest,now,write_json
from .compare_reasoning import OUT,RUN,ARMS,verify


REASONS={
 'R01':('错误商与未说明数量意义被混成单位量理解反证，未阻止该错误。','仍以“还有错误商，不只缺少解释”为由放行单位量反证。'),
 'R02':('未识别缺少说明不等于关系理解错误。','claim分项正确指出商错与单位量解释不同；uncertainty又额外指责除法反证，忽略已有错误商，拒绝理由并非全部成立。'),
 'R03':('把采用全部已提交Evidence当作依据正确，继续认可错误单位量反证。','仍以Evidence关系和完整引用支持错误推断，未识别R060/R099的解释冲突。'),
 'R04':('以提示只属于旧题为由认可新题独立完成。','正确指出先总量除份数是同Task Family的方法帮助，换数字不能清除其影响。'),
 'R05':('沿用R142/R180错误独立支持，未处理先前方法帮助。','同样沿用错误独立支持；依据引用完整不代表解释正确。'),
 'R06':('正确接受计算反证与关系说明不足的区分。','正确接受计算反证与关系说明不足的区分。'),
 'R07':('正确接受无帮助更正后的有限计算支持。','正确接受无帮助更正后的有限计算支持。'),
 'R08':('正确接受定位帮助与自行求商的责任区分。','正确接受定位帮助与自行求商的责任区分。'),
 'R09':('正确接受方法帮助替代关系识别但未替代求商。','正确接受方法帮助替代关系识别但未替代求商。'),
 'R10':('正确接受正反计算材料并存及关系Claim合法UNKNOWN/UNCHANGED。','正确接受正反计算材料并存及关系Claim合法UNKNOWN/UNCHANGED。'),
 'R11':('正确接受承认定位帮助的合法提示理由。','正确接受承认定位帮助的合法提示理由。'),
 'R12':('点名算式却声称未替代定位仍被放行，理由自相矛盾。','正确指出已提供定位，拒绝直接否认定位帮助的理由。'),
}
GENERATIONS={
 ('R13','disabled'):(True,True,'单位量说明为NonInformative，错误商分别解释为整题和除法反证；保留单样本限制。'),
 ('R13','high'):(False,False,'没有数量意义说明，却以44÷4算式结构支持要求自己说明意义的R027；不符合冻结的NonInformative准则。不是要求证明掌握，而是未观察到该Claim要求的说明行为。'),
 ('R14','disabled'):(False,False,'继续采用R060错误单位量反证，与R099的缺失不等于错误并列，维持反向DIRECTIONAL。'),
 ('R14','high'):(False,False,'虽然复述缺少解释不足判断，仍使用R060作有限反向证据，未修复错误传播。'),
 ('R15','disabled'):(False,False,'将原方法提示限于旧题，并把影响后续新题称为倒灌，仍支持无帮助整题Claim。'),
 ('R15','high'):(False,False,'R089的方法帮助被限于旧题，新题仍被称为独立完成；与本组R04正确拒绝同类理由形成不一致。'),
 ('R16','disabled'):(False,False,'保留R142/R180对无帮助整题的错误支持，新的有限措辞未纠正实际依据。'),
 ('R16','high'):(False,False,'保留相同错误独立支持，把新题称为独立换题；单位量UNKNOWN与计算有限支持不能弥补整题责任错误。'),
}


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def distribution(values):
    values=sorted(values)
    return {'n':len(values),'median':statistics.median(values),'p95_nearest_rank':values[math.ceil(len(values)*.95)-1],'max':values[-1]}


def main():
    if (OUT/'assessment.json').exists():raise SystemExit('RefusingToOverwriteClosedAssessment')
    frozen=read(OUT/'freeze.json');verify(frozen)
    write_json(OUT/'measured-source-verification.json',{'created':now(),'files':len(frozen['source_sha256']),'changed_sources_during_execution':[]})
    errors=[];units=[];arms={};calls={}
    with zipfile.ZipFile(OUT/'source.zip') as archive:
        for name,expected in frozen['source_sha256'].items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=expected:errors.append('ArchiveMismatch:'+name)
    for arm in ARMS:
        current={p.stem:read(p) for p in (RUN/arm).rglob('attempt_*.json')};calls.update(current)
        for case in frozen['spec']['cases']:
            result=read(OUT/'items'/f'{case["id"]}-{arm}.json');attempt=result['attempts'][0]
            if result['input_sha256']!=case['input_sha256']:errors.append('InputMismatch:'+case['id'])
            unit={'case':case['id'],'arm':arm,'purpose':case['purpose'],'role':case['role'],
                  'primary_status':attempt['status'],'recovery_count':len(result['attempts'])-1,
                  'attempt_id':attempt.get('attempt_id'),'trace':f'items/{case["id"]}-{arm}.json'}
            if case['role']=='review':
                matched=attempt.get('label_matched',False)
                reason_status='PARTIAL' if case['id']=='R02' and arm=='high' else 'CORRECT' if matched else 'INCORRECT'
                unit.update(expected=case['expected'],effective_verdict=attempt.get('effective_verdict'),label_matched=matched,
                  reason_quality=reason_status,reason=REASONS[case['id']][int(arm=='high')])
            else:
                target,usable,reason=GENERATIONS[(case['id'],arm)]
                unit.update(target_met=target,whole_output_usable=usable,reason=reason)
            units.append(unit)
        successes=[c for c in current.values() if c['status']=='COMPLETED']
        rows=[u for u in units if u['arm']==arm];ev=[u for u in rows if u['role']=='review' and u['purpose']!='Policy']
        pos=[u for u in ev if u['expected']=='PASS'];neg=[u for u in ev if u['expected']=='FAIL']
        ip=sum(c.get('usage',{}).get('prompt_tokens',0) for c in current.values());op=sum(c.get('usage',{}).get('completion_tokens',0) for c in current.values())
        arms[arm]={'evaluation_labels_matched':sum(u['label_matched'] for u in ev),'evaluation_review_cases':len(ev),
          'fully_correct_review_labels_and_reasons':sum(u['label_matched'] and u['reason_quality']=='CORRECT' for u in ev),
          'false_accepts':sum(u['effective_verdict']=='PASS' for u in neg),'negative_cases':len(neg),
          'false_rejects':sum(u['effective_verdict']=='FAIL' for u in pos),'positive_cases':len(pos),
          'policy_labels_matched':sum(u.get('label_matched',False) for u in rows if u['purpose']=='Policy'),'policy_cases':2,
          'generation_targets_met':sum(u.get('target_met',False) for u in rows),'generation_whole_usable':sum(u.get('whole_output_usable',False) for u in rows),'generation_cases':4,
          'http_attempts':len(current),'logical_requests':len({c['logical_id'] for c in current.values()}),
          'transport_failures':sum(bool(c.get('transport_failure')) for c in current.values()),
          'primary_format_failures':sum(u['primary_status']!='COMPLETED' for u in rows),'format_recoveries':sum(u['recovery_count'] for u in rows),
          'confirmed_input_tokens':ip,'confirmed_output_tokens':op,'confirmed_usage_peak_estimate_cny':(ip*2+op*8)/1_000_000,
          'successful_request_api_seconds':distribution([c['seconds'] for c in successes]),'promising_for_next_live_experiment':False}
    budget=read(OUT/'api-budget.json')
    if set(calls)!=set(budget['reservations']) or len(calls)!=budget['total_attempts']:errors.append('AttemptAccountingMismatch')
    groups=defaultdict(list)
    for c in calls.values():groups[c['logical_id']].append(c)
    unrecovered=[key for key,values in groups.items() if any(c.get('transport_failure') for c in values) and not any(c['status']=='COMPLETED' for c in values)]
    if unrecovered:errors.append('UnrecoveredTransport')
    # Compare actual transmitted messages, not just the declared fixture hashes.
    for case in frozen['spec']['cases']:
        pair=[]
        for arm in ARMS:
            r=read(OUT/'items'/f'{case["id"]}-{arm}.json');c=calls[r['attempts'][0]['attempt_id']]
            pair.append(digest({'messages':c['messages'],'schema':c['schema']}))
            expected_system=case['system']+'\n输出 JSON schema：'+__import__('architecture_validation.common',fromlist=['dumps']).dumps(case['schema'])
            if c['messages'][0]['content']!=expected_system or json.loads(c['messages'][1]['content'])!=case['context']:errors.append('ActualInputChanged:'+case['id']+':'+arm)
        if len(set(pair))!=1:errors.append('UnpairedInput:'+case['id'])
    for arm in ARMS:
        ids={p.stem for p in (RUN/arm).rglob('attempt_*.json')}
        arms[arm]['conservative_cny']=sum(budget['reservations'][i].get('actual_estimated_cny',budget['reservations'][i]['cost']) for i in ids)
    write_json(OUT/'quality-review.json',{'created':now(),'reviewer':'Implementation author / Codex; not independent blinded human assessment','units':units})
    result={'created':now(),'status':'CLOSED_NO_PROMISING_ARM','gate_G2':'HOLD','formal_calls':0,'arms':arms,
      'resources':{'http_attempts':len(calls),'logical_requests':len(groups),'transport_failures':sum(bool(c.get('transport_failure')) for c in calls.values()),'unrecovered_transport':unrecovered,
        'confirmed_input_tokens':sum(a['confirmed_input_tokens'] for a in arms.values()),'confirmed_output_tokens':sum(a['confirmed_output_tokens'] for a in arms.values()),
        'confirmed_usage_peak_estimate_cny':sum(a['confirmed_usage_peak_estimate_cny'] for a in arms.values()),'conservative_cny':budget['estimated_cny'],'active_seconds':budget['active_b4_seconds']},
      'integrity':{'errors':errors,'paired_exact_inputs_verified':16,'attempt_records_verified':len(calls),'frozen_source_files_verified':len(frozen['source_sha256']),
        'actual_response_model_aliases':dict(Counter(c.get('response_model') for c in calls.values() if c.get('response_model')))},
      'decision':'Neither arm meets the predeclared next-experiment screen. Keep the default non-thinking profile; no live or full G2 follow-on in this campaign. Model alias is recorded, not a pinned provider weight version.',
      'limitations':'One primary response per arm per author-known case. Generation cases are independent replays of original contexts, not a connected end-to-end recovery. This experiment does not evaluate a high-mode reviewer on newly generated disabled-mode candidates.'}
    write_json(OUT/'assessment.json',result)
    write_json(OUT/'decision.json',{'created':now(),'promising_arm':None,'deploy':False,'formal_admitted':False,'status':'CLOSED','reason':'Critical R01/R03/R05 remain false accepts; all high-mode generations miss their frozen targets.'})
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
