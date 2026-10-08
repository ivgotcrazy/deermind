"""One bounded R3 repair check, then at most one admitted full G2 reassessment."""
import argparse
import hashlib
import json
import time
import zipfile

from .common import BASE,ROOT,Rejected,now,write_json
from .contracts import validate
from .model import Budget,RealModel,load_config
from .protocols import system,review_system
from .review import aggregate_review
from .revalidate import prepare_probe
from .validate_g2 import run_session,verify_frozen,probes

OUT=BASE/'reports/evaluation-repair-r3'
RUN=BASE/'runs/evaluation-repair-r3'
BUDGET=OUT/'api-budget.json'
POLICY={'category_limits':{'B2':140,'base':240,'repair':24,'probe':12,'transport':24},
        'total_attempts':440,'development_segment_attempts':140,'input_tokens':4_000_000,
        'output_tokens':1_000_000,'cny':20,'active_seconds':2700,'active_all_phases':True}


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def initialize():
    if (OUT/'freeze.json').exists():return read(OUT/'freeze.json')
    OUT.mkdir(parents=True,exist_ok=True)
    spec=read(BASE/'fixtures/evaluation-repair-r3.json')
    files=[p for p in BASE.rglob('*') if p.is_file() and not {'reports','runs','__pycache__'}.intersection(p.relative_to(BASE).parts)]
    files+=list((ROOT/'doc/system-design/build').glob('*.md'))
    manifest={}
    with zipfile.ZipFile(OUT/'source.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in files:
            name=p.relative_to(ROOT).as_posix();raw=p.read_bytes();manifest[name]=hashlib.sha256(raw).hexdigest();z.writestr(name,raw)
    if BUDGET.exists():raise Rejected('ExistingUnfrozenBudget')
    b=Budget(BUDGET);b.data['policy']=POLICY;b.data['campaign']='Evaluation-repair-R3';b.save()
    f={'created':now(),'source_sha256':manifest,'policy':POLICY,'spec':spec,'formal_probes':probes(),
       'model':{k:v for k,v in load_config().items() if k!='api_key'},
       'parameters':{'thinking':'disabled','temperature':0,'max_tokens':8192,'timeout':60},
       'scope':'One targeted revision; no automatic semantic tuning loop. Formal stage requires recorded author admission.'}
    write_json(OUT/'freeze.json',f);return f


def replay_all(frozen):
    dest=OUT/'replays.json'
    if dest.exists():raise Rejected('RefusingToOverwriteReplays')
    model=RealModel('B2',RUN/'replays/model-calls',BUDGET);result={'created':now(),'status':'RUNNING','items':[]};start=time.monotonic()
    for case in frozen['spec']['replays']:
        value={k:case[k] for k in ('id','purpose','role','expected','criterion','source')}
        try:
            prompt=review_system(case['purpose']) if case['role']=='review' else system(case['purpose'])
            output,rec=model.complete(prompt,case['context'],case['schema'],case['role']+':'+case['purpose'],'probe')
            validate(case['schema'],output)
            value.update(status='COMPLETED',output=output,attempt_id=rec['attempt_id'])
            if case['role']=='review':
                effective=aggregate_review(output);passed=effective=='PASS'
                value.update(effective_verdict=effective,accepted=passed,matched=passed if case['expected']=='PASS' else effective=='FAIL')
            else:value['author_assessment']='PENDING'
        except Rejected as exc:value.update(status='FAILED',failure=str(exc))
        result['items'].append(value);write_json(dest,result)
        print(json.dumps({'replay':case['id'],'status':value['status'],'matched':value.get('matched')},ensure_ascii=False),flush=True)
        if any(mark in value.get('failure','') for mark in ('BudgetExhausted','Transport','ProviderHTTP','LocalBudget')):
            result.update(status='RESOURCE_OR_NETWORK_PAUSE',stop_reason=value['failure']);break
    if result['status']=='RUNNING':result['status']='MEASURED'
    result.update(completed=now(),wall_seconds=time.monotonic()-start);write_json(dest,result)
    model.budget.refresh_active();model.budget.save();return result


def formal_probes(frozen):
    dest=OUT/'formal/probes.json'
    if dest.exists():raise Rejected('RefusingToOverwriteProbes')
    result={'created':now(),'status':'RUNNING','items':[]};start=time.monotonic()
    model=RealModel('B4',RUN/'formal/probes/model-calls',BUDGET)
    for probe in frozen['formal_probes']:
        value={k:probe[k] for k in ('id','purpose','expected')}
        try:
            sem,schema,_=prepare_probe(probe);output,rec=model.complete(review_system(probe['purpose']),sem,schema,'Probe:'+probe['purpose'],'probe');validate(schema,output)
            effective=aggregate_review(output);accepted=effective=='PASS'
            value.update(status='COMPLETED',output=output,effective_verdict=effective,attempt_id=rec['attempt_id'],accepted=accepted,matched=accepted if probe['expected']=='PASS' else effective in ('FAIL','UNRESOLVED'))
        except Rejected as exc:value.update(status='FAILED',failure=str(exc))
        result['items'].append(value);write_json(dest,result);print(json.dumps({'probe':probe['id'],'status':value['status'],'matched':value.get('matched')}),flush=True)
        if any(mark in value.get('failure','') for mark in ('BudgetExhausted','Transport','ProviderHTTP','LocalBudget')):
            result.update(status='RESOURCE_OR_NETWORK_PAUSE',stop_reason=value['failure']);break
    if result['status']=='RUNNING':result['status']='MEASURED'
    result.update(completed=now(),wall_seconds=time.monotonic()-start);write_json(dest,result);model.budget.refresh_active();model.budget.save()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('development','formal'));args=parser.parse_args()
    if args.stage=='formal' and (not (OUT/'admission.json').exists() or not read(OUT/'admission.json').get('admitted')):
        raise SystemExit('Formal stage requires completed author-reviewed admission; no API call made')
    frozen=initialize();verify_frozen(frozen)
    if read(BUDGET)['policy']!=POLICY:raise SystemExit('BudgetPolicyChanged')
    if args.stage=='development':
        if not (OUT/'replays.json').exists():replay_all(frozen)
        if read(OUT/'replays.json')['status']!='MEASURED':raise SystemExit('Inspect incomplete replays')
        cases=frozen['spec']['live'];phase='B2'
    else:cases=frozen['spec']['formal']['sessions'];phase='B4'
    for case in cases:
        dest=OUT/args.stage/(case['id']+'.json')
        if dest.exists():
            if read(dest)['status']!='MEASURED':raise SystemExit('Inspect unfinished '+case['id'])
            continue
        report=run_session(case,RUN/args.stage/case['id'],dest,phase=phase,budget_path=BUDGET);verify_frozen(frozen)
        if report['status']!='MEASURED':raise SystemExit(report['status'])
    if args.stage=='formal' and not (OUT/'formal/probes.json').exists():formal_probes(frozen)
    verify_frozen(frozen)
    write_json(OUT/(args.stage+'-execution.json'),{'created':now(),'status':'MEASURED','changed_sources_during_run':[],'budget':read(BUDGET),'assessment':'PENDING'})


if __name__=='__main__':main()
