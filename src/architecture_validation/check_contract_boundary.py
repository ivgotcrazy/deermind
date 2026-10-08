"""One frozen, bounded development check; never admits a formal G2 campaign."""
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
from .model import Budget,RealModel,load_config
from .protocols import review_system
from .revalidate import prepare_probe


REPORTS=BASE/'reports/contract-boundary-v1'
RUN=BASE/'runs/contract-boundary-v1'
POLICY={'category_limits':{'B2':40,'base':0,'repair':0,'probe':0,'transport':0},
        'total_attempts':40,'development_segment_attempts':40,'input_tokens':800000,
        'output_tokens':160000,'cny':5,'active_seconds':900,'active_all_phases':True}
INPUTS=[
    {'text':'42÷6＝8，8×15＝120。我想看完整讲解，请给出计算过程和答案。'},
    {'text':'刚才没有看到系统讲解。我的计算仍是42÷6＝8，8×15＝120。请完整讲解。',
     'after_explanation':'看了刚才的讲解后，我写下42÷6＝7，7×15＝105，因为先求每份价格再乘15份。这是参考讲解写的。'}]


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def has_explanation(rows):
    intents={(r['obj'],r['revision'],r['hash']):r for r in rows if r['kind']=='ActionIntent'}
    for row in rows:
        if row['kind']!='ActionOccurrence' or not row['body']['blocks']:continue
        ref=row['body']['intent_ref'];intent=intents.get((ref['id'],ref['revision'],ref['content_hash']))
        if intent and intent['body']['action_type']=='Explanation':return True
    return False


def main(*,reports=REPORTS,run=RUN,probe_ids=('P01','P05','P06')):
    reports.mkdir(parents=True,exist_ok=True)
    dest=reports/'result.json';budget_path=reports/'api-budget.json'
    if run.exists() or dest.exists() or budget_path.exists():
        raise SystemExit('Refusing to repeat or overwrite this bounded check')
    probes=deepcopy([p for p in read(BASE/'fixtures/development-probes-r1.json') if p['id'] in probe_ids])
    for probe in probes:
        if probe['purpose']=='Observation':probe['candidate'].pop('current_purpose',None)
    files=[p for p in BASE.rglob('*') if p.is_file() and not {'runs','reports','__pycache__'}.intersection(p.relative_to(BASE).parts)]
    files+=list((ROOT/'doc/system-design/build').glob('*.md'))+[ROOT/'deermind.cmd',ROOT/'scripts/deermind.ps1']
    manifest={}
    with zipfile.ZipFile(reports/'source.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for p in files:
            name=p.relative_to(ROOT).as_posix();data=p.read_bytes()
            manifest[name]=hashlib.sha256(data).hexdigest();archive.writestr(name,data)
    write_json(reports/'freeze.json',{'created':now(),'source_sha256':manifest,'policy':POLICY,
        'inputs':INPUTS,'task':{'quantity':6,'total':42,'target':15},'probes':probes,
        'model':{k:v for k,v in load_config().items() if k!='api_key'},
        'parameters':{'thinking':'disabled','temperature':0,'max_tokens':8192,'timeout':60},
        'purpose':'Development check only; G2 HOLD unchanged'})
    budget=Budget(budget_path);budget.data['policy']=POLICY;budget.data['campaign']=reports.name.upper();budget.save()
    report={'created':now(),'status':'RUNNING','turns':[],'probes':[],'gate_G2':'HOLD','formal_campaign_started':False,
            'scope':reports.name,'planned_turns':len(INPUTS),'planned_probes':len(probes)}
    write_json(dest,report);started=time.monotonic();stop=False
    with Server(run,'real','B2',budget_path=budget_path) as srv,sync_playwright() as pw:
        browser=pw.chromium.launch();sid='boundary';q=srv.task('boundary');page=srv.page(browser,sid,q)
        for index,item in enumerate(INPUTS,1):
            rows=srv.records(sid)
            explained=has_explanation(rows)
            text=item.get('after_explanation',item['text']) if explained else item['text']
            before=time.perf_counter();turn=srv.submit(sid,text,q,str(index));settled=srv.settled(sid,turn['id'],900)
            report['turns'].append(settled|{'text':text,'seconds':time.perf_counter()-before,'prior_explanation':explained})
            write_json(dest,report)
            print(json.dumps({'turn':index,'status':settled['status'],'error':settled['error']},ensure_ascii=False),flush=True)
            if settled['status']=='WAITING_EFFECT':page.evaluate('window.stopChannel()')
            if any(marker in settled['error'] for marker in ('BudgetExhausted','Transport','ProviderHTTP','LocalBudget')):
                stop=True;report['stop_reason']=settled['error'];break
        report['browser']={'text':page.locator('#conversation').inner_text(),'rendered':page.evaluate('window.buildTest.rendered')}
        page.screenshot(path=str(run/'browser.png'),full_page=True);srv.export();browser.close()
    if not stop and probes:
        model=RealModel('B2',run/'model-calls',budget_path)
        for probe in probes:
            value={'id':probe['id'],'expected':probe['expected']}
            try:
                sem,schema,mapping=prepare_probe(probe)
                output,record=model.complete(review_system(probe['purpose']),sem,schema,'Probe:'+probe['purpose'],'probe')
                validate(schema,output)
                accepted=output['verdict']=='PASS' and all(check['verdict']=='PASS' for check in output['checks'])
                value.update(status='COMPLETED',output=output,attempt_id=record['attempt_id'],accepted=accepted,
                             matched=accepted if probe['expected']=='PASS' else output['verdict'] in ('FAIL','UNRESOLVED'))
            except Rejected as exc:
                value.update(status='FAILED',failure=str(exc))
                stop=True;report['stop_reason']=str(exc)
            report['probes'].append(value);write_json(dest,report)
            print(json.dumps({'probe':probe['id'],'status':value['status'],'matched':value.get('matched')}),flush=True)
            if stop:break
        model.budget.refresh_active();model.budget.save()
    changed=[name for name,sha in manifest.items() if not (ROOT/name).exists() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha]
    report.update(status='STOPPED' if stop else 'COMPLETED',completed=now(),wall_seconds=time.monotonic()-started,
                  budget=read(budget_path),changed_sources_during_run=changed)
    write_json(dest,report)
    if changed:raise SystemExit('Sources changed during frozen run')


if __name__=='__main__':main()
