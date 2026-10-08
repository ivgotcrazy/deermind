"""R2 coverage campaign, preserving all earlier runs and the original G2 criteria."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
import zipfile

from playwright.sync_api import sync_playwright

from .common import BASE,ROOT,Rejected,now,write_json
from .contracts import validate
from .harness import Server
from .measure import packet
from .model import Budget,RealModel,load_config
from .protocols import review_system
from .revalidate import prepare_probe,select_input
from .review import aggregate_review

OUT=BASE/'reports/g2-r2'
BUDGET=OUT/'api-budget.json'
POLICY={'category_limits':{'B2':0,'base':320,'repair':48,'probe':12,'transport':40},
        'total_attempts':420,'input_tokens':4_000_000,'output_tokens':1_000_000,
        'cny':50,'active_seconds':5400,'active_all_phases':True}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def probes():
    result=deepcopy(read(BASE/'fixtures/probes-r1.json'))
    for item in result:
        if item['purpose']=='Observation':item['candidate'].pop('current_purpose',None)
    return result


def initialize(scope=OUT):
    if (scope/'freeze.json').exists():return read(scope/'freeze.json')
    if BUDGET.exists() and read(BUDGET)['policy']!=POLICY:raise SystemExit('Budget policy changed')
    scope.mkdir(parents=True,exist_ok=True)
    files=[p for p in BASE.rglob('*') if p.is_file() and not {'runs','reports','__pycache__'}.intersection(p.relative_to(BASE).parts)]
    files+=list((ROOT/'doc/system-design/build').glob('*.md'))
    manifest={}
    with zipfile.ZipFile(scope/'source.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in files:
            data=p.read_bytes();name=p.relative_to(ROOT).as_posix()
            manifest[name]=hashlib.sha256(data).hexdigest();z.writestr(name,data)
    frozen={'created':now(),'source_sha256':manifest,'budget_policy':POLICY,
            'spec':read(BASE/'fixtures/holdout-r1.json'),'probes':probes(),
            'model':{k:v for k,v in load_config().items() if k!='api_key'},
            'parameters':{'thinking':'disabled','temperature':0,'max_tokens':8192,'timeout':60},
            'admission':{'basis':'Latest 62 offline checks plus real two-turn explanation/evaluation/policy chain; user authorized remaining G2 validation.',
                         'prior_R1_admission_unchanged':True},
            'independence':'Previously prepared, unexecuted R1 formal instances; author-known scenario families, not independent blinded evaluation.'}
    if not BUDGET.exists():
        b=Budget(BUDGET);b.data['policy']=POLICY;b.data['campaign']='G2-R2';b.save()
    write_json(scope/'freeze.json',frozen)
    return frozen


def verify_frozen(frozen):
    changed=[p for p,h in frozen['source_sha256'].items() if not (ROOT/p).exists() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    if changed:raise Rejected('FrozenSourcesChanged:'+','.join(changed))


def needs_inspection(reason):
    # Error codes only; this never classifies learner language or semantic meaning.
    return reason.startswith(('ImplementationError:','LocalBudget','SchemaMismatch',
        'InvalidStructuredOutput','IncompleteModelOutput','UnknownOrWrongSource',
        'ClaimCoverageMismatch','UnchangedAssessmentMismatch','ReviewUnknownSource'))


def run_session(case,path,dest,*,model='real',budget_path=BUDGET,phase='B4'):
    if path.exists() or dest.exists():raise Rejected('RefusingToOverwriteSession')
    report={'created':now(),'id':case['id'],'status':'RUNNING','turns':[],'coverage_notes':[]}
    packets=[];started=time.monotonic();write_json(dest,report)
    with Server(path,model,phase,budget_path=budget_path) as srv,sync_playwright() as pw:
        browser=pw.chromium.launch();sid=case['id']
        tasks=[srv.request('/admin/canonical',p,True)['id'] for p in case['tasks']]
        page=srv.page(browser,sid,tasks[0],{'maxBlocks':1} if case.get('partial') else None)
        try:
            for n,item in enumerate(case['inputs'],1):
                rows=srv.records(sid);text,branch=select_input(item,report,rows)
                q=tasks[item.get('task',0)];label=f'{sid}.{n}'
                page.locator('#task').evaluate('(node,text)=>node.textContent=text',case['tasks'][item.get('task',0)]['body']['statement'])
                correction=None
                if item.get('correct_turn'):
                    old=report['turns'][item['correct_turn']-1]['id']
                    observations=[r for r in rows if r['kind']=='Observation' and r['turn_id']==old]
                    if observations:correction=observations[-1]['id']
                    else:report['coverage_notes'].append(label+': required correction target unavailable')
                if item.get('fault'):srv.request('/admin/test/fault',{'purpose':item['fault']},True)
                start=time.perf_counter();turn=srv.submit(sid,text,q,str(n),correction)
                result=srv.settled(sid,turn['id'],900)
                if item.get('fault'):srv.request('/admin/test/fault',{'purpose':None},True)
                if result['status']=='WAITING_EFFECT':
                    page.evaluate('window.stopChannel()')
                    result=srv.settled(sid,turn['id'],30)
                    report['coverage_notes'].append(label+': channel reconciliation required')
                result.update(label=label,wall_seconds=time.perf_counter()-start,
                              injected_fault=item.get('fault'),branch=branch)
                report['turns'].append(result)
                rows=srv.records(sid);packets.append(packet(rows,result,{'text':text,'branch':branch,'frozen_spec':item}))
                write_json(path/'review-packets.json',packets);write_json(dest,report)
                print(json.dumps({'unit':label,'status':result['status'],'error':result['error'],'seconds':round(result['wall_seconds'],2)}),flush=True)
                if needs_inspection(result['error']):
                    report.update(status='IMPLEMENTATION_INSPECTION_REQUIRED',stop_reason=result['error']);break
                if any(marker in result['error'] for marker in ('BudgetExhausted','Transport','ProviderHTTP')):
                    report.update(status='RESOURCE_OR_NETWORK_PAUSE',stop_reason=result['error']);break
            report['browser']={'text':page.locator('#conversation').inner_text(),'rendered':page.evaluate('window.buildTest.rendered')}
            page.screenshot(path=str(path/'browser.png'),full_page=True)
            if report['status']=='RUNNING':report['status']='MEASURED'
        except Exception as exc:
            report.update(status='DRIVER_ERROR',stop_reason=type(exc).__name__+':'+str(exc))
            raise
        finally:
            srv.export();browser.close()
            report.update(completed=now(),wall_seconds=time.monotonic()-started)
            write_json(dest,report)
    return report


def run_probes(frozen,scope=OUT,run_root=BASE/'runs/g2-r2'):
    dest=scope/'probes.json'
    if dest.exists():raise Rejected('RefusingToOverwriteProbes')
    result={'created':now(),'status':'RUNNING','items':[]};started=time.monotonic()
    model=RealModel('B4',run_root/'probes/model-calls',BUDGET)
    for probe in frozen['probes']:
        value={'id':probe['id'],'purpose':probe['purpose'],'expected':probe['expected']}
        try:
            sem,schema,mapping=prepare_probe(probe)
            output,record=model.complete(review_system(probe['purpose']),sem,schema,'Probe:'+probe['purpose'],'probe')
            validate(schema,output)
            complete=True  # Strict prefixItems enforces every required rule/Claim.
            effective=aggregate_review(output);accepted=effective=='PASS'
            value.update(status='COMPLETED',output=output,accepted=accepted,review_complete=complete,
                attempt_id=record['attempt_id'],effective_verdict=effective,matched=accepted if probe['expected']=='PASS' else effective in ('FAIL','UNRESOLVED'))
        except Rejected as exc:
            value.update(status='FAILED',failure=str(exc),matched=False)
        result['items'].append(value);write_json(dest,result)
        print(json.dumps({'probe':probe['id'],'status':value['status'],'matched':value['matched']}),flush=True)
        if any(marker in value.get('failure','') for marker in ('BudgetExhausted','Transport','ProviderHTTP')):
            result.update(status='RESOURCE_OR_NETWORK_PAUSE',stop_reason=value['failure']);break
    if result['status']=='RUNNING':result['status']='MEASURED'
    result.update(completed=now(),wall_seconds=time.monotonic()-started);write_json(dest,result)
    model.budget.refresh_active();model.budget.save()
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--session',choices=[f'S{i}' for i in range(1,7)])
    parser.add_argument('--revision',choices=('v1','v2'),default='v1')
    parser.add_argument('--probes-only',action='store_true');args=parser.parse_args()
    scope=OUT if args.revision=='v1' else OUT/args.revision
    run_root=BASE/'runs/g2-r2' if args.revision=='v1' else BASE/'runs/g2-r2'/args.revision
    frozen=initialize(scope);verify_frozen(frozen)
    if not args.probes_only:
        for case in frozen['spec']['sessions']:
            if args.session and case['id']!=args.session:continue
            dest=scope/(case['id']+'.json')
            if dest.exists():
                if read(dest)['status']!='MEASURED':raise SystemExit('Inspect unfinished session '+case['id']+' before continuing')
                continue
            report=run_session(case,run_root/case['id'],dest)
            verify_frozen(frozen)
            if report['status']!='MEASURED':raise SystemExit(report['status'])
    if not args.session and not (scope/'probes.json').exists():run_probes(frozen,scope,run_root)
    verify_frozen(frozen)
    write_json(scope/'execution-state.json',{'created':now(),'session_status':{p.stem:read(p)['status'] for p in scope.glob('S?.json')},
        'probes_status':read(scope/'probes.json')['status'] if (scope/'probes.json').exists() else 'NOT_STARTED',
        'gate_G2':'ASSESSMENT_PENDING','budget':read(BUDGET),'changed_sources_during_run':[]})


if __name__=='__main__':main()
