"""One bounded R1 campaign with separate immutable attempts and no gate inflation."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
import zipfile
from playwright.sync_api import sync_playwright

from .common import BASE, ROOT, Rejected, now, write_json
from .contracts import WIRE, validate
from .harness import Server
from .measure import packet
from .model import Budget, RealModel
from .protocols import RULES, review_system,review_rule_ids

REPORTS=BASE/'reports/revalidation-r1'
BUDGET=REPORTS/'api-budget.json'
POLICY={'category_limits':{'B2':160,'base':240,'repair':24,'probe':12,'transport':24},
        'total_attempts':460,'development_segment_attempts':80,'input_tokens':4_000_000,
        'output_tokens':1_000_000,'cny':50,'active_seconds':5400,'active_all_phases':True}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def freeze(name):
    files=[p for p in BASE.rglob('*') if p.is_file() and not {'runs','reports','__pycache__'}.intersection(p.relative_to(BASE).parts)]
    files+=list((ROOT/'doc/system-design/build').glob('*.md'))
    manifest={}
    with zipfile.ZipFile(REPORTS/(name+'-source.zip'),'x',zipfile.ZIP_DEFLATED) as z:
        for p in files:
            rel=p.relative_to(ROOT).as_posix();data=p.read_bytes()
            manifest[rel]=hashlib.sha256(data).hexdigest();z.writestr(rel,data)
    value={'created':now(),'source_sha256':manifest,'budget_policy':POLICY,
           'model':{k:v for k,v in __import__('architecture_validation.model',fromlist=['load_config']).load_config().items() if k!='api_key'},
           'parameters':{'thinking':'disabled','temperature':0,'max_tokens':8192,'timeout':60}}
    write_json(REPORTS/(name+'-freeze.json'),value)
    return value


def select_input(item,session,rows):
    text=item['text'];condition=item.get('after_display_turn');branch='base'
    if condition:
        tid=session['turns'][condition-1]['id']
        displayed=any(r['kind']=='ActionOccurrence' and r['turn_id']==tid and r['body']['blocks'] for r in rows)
        if displayed:text=item['with_display_text'];branch='confirmed-display'
        else:branch='no-confirmed-display'
    return text,branch


def prepare_probe(probe):
    context=deepcopy(probe['context']);ids=[]
    for key,value in context.items():
        if isinstance(value,dict) and 'id' in value:ids.append(value['id'])
        if isinstance(value,list):ids += [r['id'] for r in value if isinstance(r,dict) and 'id' in r]
    ids=list(dict.fromkeys(ids));mapping={rid:f'R{i:03d}' for i,rid in enumerate(ids,1)}
    def project(value):
        if isinstance(value,str):return mapping.get(value,value)
        if isinstance(value,list):return [project(v) for v in value]
        if isinstance(value,dict):
            if set(value)=={'kind','id','version','revision','content_hash'}:
                rid=f"{value['kind']}:{value['id']}:{value['version']}"
                return {'kind':value['kind'],'id':mapping[rid]} if rid in mapping else {'kind':value['kind'],'binding':'backend-only'}
            return {k:project(v) for k,v in value.items()}
        return value
    sem=project(context);sem['candidate']=project(probe['candidate'])
    schema=deepcopy(WIRE['Review']);schema['properties']['checks']['items']['properties']['source_ids']={'type':'array','items':{'type':'string','enum':list(mapping.values())},'uniqueItems':True}
    check=schema['properties']['checks']['items'];ordered=[]
    for name in review_rule_ids(probe['purpose'],[c['id'] for c in sem.get('claims',[])]):
        bound=deepcopy(check);bound['properties']['rule_id']={'const':name};ordered.append(bound)
    schema['properties']['checks']={'type':'array','prefixItems':ordered,'items':False,'minItems':len(ordered),'maxItems':len(ordered)}
    return sem,schema,mapping


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['dev1','dev2','formal']);args=parser.parse_args()
    formal=args.stage=='formal';name='r1-'+args.stage;path=BASE/'runs'/name;dest=REPORTS/(name+'.json')
    if path.exists() or dest.exists():raise SystemExit('Refusing to repeat or overwrite a campaign segment')
    if args.stage=='dev2' and not (REPORTS/'r1-dev1.json').exists():raise SystemExit('Development order violation')
    if formal and (not (REPORTS/'admission.json').exists() or not read(REPORTS/'admission.json').get('admitted')):raise SystemExit('Formal campaign requires documented development admission')
    if not BUDGET.exists():
        b=Budget(BUDGET);b.data['policy']=POLICY;b.data['campaign']='R1';b.save()
    if read(BUDGET)['policy']!=POLICY:raise SystemExit('Budget policy mismatch')
    frozen=freeze(name)
    spec=read(BASE/'fixtures'/('holdout-r1.json' if formal else 'development-r1.json'))
    probes=read(BASE/'fixtures'/('probes-r1.json' if formal else 'development-probes-r1.json'))
    report={'created':now(),'stage':args.stage,'status':'RUNNING','sessions':[],'probes':[],
            'source_freeze':str((REPORTS/(name+'-freeze.json')).relative_to(ROOT)),
            'planned_turns':spec['planned_turns'],'planned_probes':len(probes),'active_segments':[]}
    packets=[];stopped=False;phase='B4' if formal else 'B2';started=time.monotonic();before=read(BUDGET)['active_b4_seconds']
    write_json(dest,report)
    with Server(path,'real',phase,budget_path=BUDGET) as srv,sync_playwright() as pw:
        browser=pw.chromium.launch()
        for case in spec['sessions']:
            sid=case['id'];tasks=[srv.request('/admin/canonical',p,True)['id'] for p in case['tasks']]
            page=srv.page(browser,sid,tasks[0],{'maxBlocks':1} if case.get('partial') else None)
            session={'id':sid,'turns':[],'coverage_notes':[]};report['sessions'].append(session)
            for n,item in enumerate(case['inputs'],1):
                q=tasks[item.get('task',0)];label=f'{sid}.{n}';rows=srv.records(sid)
                text,branch=select_input(item,session,rows)
                page.locator('#task').evaluate('(node,text)=>node.textContent=text',case['tasks'][item.get('task',0)]['body']['statement'])
                correction=None
                if item.get('correct_turn'):
                    previous=session['turns'][item['correct_turn']-1]['id']
                    obs=[r for r in rows if r['kind']=='Observation' and r['turn_id']==previous]
                    if obs:correction=obs[-1]['id']
                    else:session['coverage_notes'].append(label+': correction target unavailable')
                if item.get('fault'):srv.request('/admin/test/fault',{'purpose':item['fault']},True)
                begin=time.perf_counter();turn=srv.submit(sid,text,q,str(n),correction);result=srv.settled(sid,turn['id'],900)
                result.update(label=label,wall_seconds=time.perf_counter()-begin,injected_fault=item.get('fault'),branch=branch)
                if item.get('fault'):srv.request('/admin/test/fault',{'purpose':None},True)
                session['turns'].append(result);rows=srv.records(sid)
                packets.append(packet(rows,result,{'text':text,'branch':branch,'frozen_spec':item}))
                write_json(path/'review-packets.json',packets);write_json(dest,report)
                print(json.dumps({'unit':label,'status':result['status'],'error':result['error'],'seconds':round(result['wall_seconds'],2)},ensure_ascii=False),flush=True)
                if result['status']=='WAITING_EFFECT':page.evaluate('window.stopChannel()');session['coverage_notes'].append(label+': channel reconciliation required')
                if any(mark in result['error'] for mark in ('BudgetExhausted','Transport','ProviderHTTP','LocalBudget')):
                    stopped=True;report['stop_reason']=result['error'];break
            session['browser']={'text':page.locator('#conversation').inner_text(),'rendered':page.evaluate('window.buildTest.rendered')}
            page.screenshot(path=str(path/(sid+'.png')),full_page=True);page.close();write_json(dest,report)
            if stopped:break
        srv.export();browser.close()
    elapsed=time.monotonic()-started;b=Budget(BUDGET);b.data['active_b4_seconds']=max(b.data['active_b4_seconds'],before+elapsed);b.save()
    report['active_segments'].append({'kind':'sessions','seconds':elapsed})
    if not stopped:
        started=time.monotonic();model=RealModel(phase,path/'model-calls',BUDGET)
        for probe in probes:
            value={'id':probe['id'],'purpose':probe['purpose'],'expected':probe['expected'],'criterion':probe['criterion']}
            try:
                sem,schema,mapping=prepare_probe(probe)
                output,record=model.complete(review_system(probe['purpose']),sem,schema,'Probe:'+probe['purpose'],'probe')
                validate(schema,output)
                required={c['properties']['rule_id']['const'] for c in schema['properties']['checks']['prefixItems']}
                complete=len(output['checks'])==len(required) and {c['rule_id'] for c in output['checks']}==required
                accepted=output['verdict']=='PASS' and complete and all(c['verdict']=='PASS' for c in output['checks'])
                value.update(output=output,accepted=accepted,review_complete=complete,reference_mapping=mapping,attempt_id=record['attempt_id'],status='COMPLETED',
                    matched=accepted if probe['expected']=='PASS' else output['verdict'] in ('FAIL','UNRESOLVED') and complete)
            except Rejected as exc:value.update(status='FAILED',failure=str(exc),matched=False)
            report['probes'].append(value);write_json(dest,report)
            print(json.dumps({'unit':probe['id'],'status':value['status'],'matched':value['matched']}),flush=True)
            if any(mark in value.get('failure','') for mark in ('BudgetExhausted','Transport','ProviderHTTP','LocalBudget')):
                stopped=True;report['stop_reason']=value['failure'];break
        model.budget.refresh_active();model.budget.save();report['active_segments'].append({'kind':'probes','seconds':time.monotonic()-started})
    changed=[name for name,sha in frozen['source_sha256'].items() if not (ROOT/name).exists() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha]
    report.update(status='STOPPED' if stopped else 'COMPLETED',completed=now(),budget=read(BUDGET),changed_sources_during_run=changed)
    write_json(dest,report)
    if changed:raise SystemExit('Sources changed during frozen run')


if __name__=='__main__':main()
