"""Fixed-input R4 reasoning-mode comparison; no runtime deployment or G2 runner."""
import argparse
from copy import deepcopy
import hashlib
import json
import zipfile

from .common import BASE,ROOT,Rejected,digest,now,write_json
from .contracts import validate
from .model import Budget,RealModel,load_config
from .protocols import system,review_system
from .review import aggregate_review

OUT=BASE/'reports/reasoning-comparison-r4'
RUN=BASE/'runs/reasoning-comparison-r4'
SPEC=BASE/'fixtures/reasoning-comparison-r4.json'
BUDGET=OUT/'api-budget.json'
POLICY={'category_limits':{'B2':96,'base':0,'repair':0,'probe':0,'transport':0},
        'total_attempts':96,'development_segment_attempts':96,'input_tokens':1_500_000,
        'output_tokens':1_500_000,'cny':15,'active_seconds':1800,'active_all_phases':True}
ARMS={'disabled':{'thinking':'disabled','max_tokens':32768,'timeout':120},
      'high':{'thinking':'enabled','reasoning_effort':'high','max_tokens':32768,'timeout':120}}


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def prepare():
    if SPEC.exists():raise Rejected('RefusingToReplaceFrozenCases')
    cases=deepcopy(read(BASE/'fixtures/evaluation-repair-r3.json')['replays'])
    for case in cases:
        if case['source'].startswith('src/'):
            source=ROOT/case['source']
            if hashlib.sha256(source.read_bytes()).hexdigest()!=case['source_sha256']:raise Rejected('OriginalEvidenceChanged')
            original=read(source)
            case['context']=json.loads(original['messages'][1]['content'])
            case['schema']=original['schema']  # R2 four checks, not rejected R3 per-Claim schema.
        case['system']=review_system(case['purpose']) if case['role']=='review' else system(case['purpose'])
        case['input_sha256']=digest({k:case[k] for k in ('system','context','schema')})
    write_json(SPEC,{'version':'reasoning-comparison-r4','cases':cases,'arms':ARMS,
      'design':'One primary response per case per arm. Alternate arm order by case. Same R2 prompts, schema and exact contexts; only thinking configuration differs. Temperature is unsupported in thinking mode.',
      'format_recovery':'At most one regeneration for JSON/schema/truncation failures; primary and recovery scored separately. Never retry a semantic FAIL.',
      'decision':'Not G2 admission. A promising arm needs >=9/10 Evaluation review labels with valid reasons, all R01/R03/R04/R05 negatives correctly rejected, >=4/5 positives accepted, all four generation boundary targets met and >=3/4 whole generations usable. Compare costs and false rejections; R11/R12 Policy diagnostics separate. No automatic full G2 or deployment.'})
    return read(SPEC)


def initialize():
    if (OUT/'freeze.json').exists():return read(OUT/'freeze.json')
    spec=read(SPEC)
    if BUDGET.exists():raise Rejected('ExistingUnfrozenBudget')
    files=[p for p in BASE.rglob('*') if p.is_file() and not {'reports','runs','__pycache__','.pytest_cache'}.intersection(p.relative_to(BASE).parts)]
    files+=list((ROOT/'doc/system-design/build').glob('*.md'))
    manifest={}
    with zipfile.ZipFile(OUT/'source.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(files):
            name=p.relative_to(ROOT).as_posix();data=p.read_bytes()
            manifest[name]=hashlib.sha256(data).hexdigest();archive.writestr(name,data)
    budget=Budget(BUDGET);budget.data.update(policy=POLICY,campaign='Reasoning-comparison-R4');budget.save()
    frozen={'created':now(),'source_sha256':manifest,'spec':spec,'policy':POLICY,
      'model':{k:v for k,v in load_config().items() if k!='api_key'},'pricing':read(OUT/'pricing.json')}
    write_json(OUT/'freeze.json',frozen);return frozen


def verify(frozen):
    changed=[name for name,h in frozen['source_sha256'].items() if not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h]
    if changed:raise Rejected('FrozenSourcesChanged:'+','.join(changed))
    if read(BUDGET)['policy']!=POLICY:raise Rejected('BudgetPolicyChanged')


def run_case(case,arm):
    dest=OUT/'items'/f'{case["id"]}-{arm}.json'
    if dest.exists():return read(dest)
    model=RealModel('B2',RUN/arm/case['id']/'model-calls',BUDGET,**ARMS[arm])
    result={'created':now(),'case':case['id'],'arm':arm,'role':case['role'],'purpose':case['purpose'],
            'expected':case['expected'],'input_sha256':case['input_sha256'],'attempts':[],'author_assessment':'PENDING'}
    context=case['context']
    for index in range(2):
        item={'kind':'primary' if index==0 else 'format_recovery'}
        try:
            output,record=model.complete(case['system'],context,case['schema'],case['role']+':'+case['purpose'],'base')
            item['attempt_id']=record['attempt_id'];item['output']=output
            validate(case['schema'],output)
            item['status']='COMPLETED'
            if case['role']=='review':
                item['effective_verdict']=aggregate_review(output)
                item['label_matched']=item['effective_verdict']==case['expected']
        except Rejected as exc:item.update(status='FAILED',failure=str(exc))
        result['attempts'].append(item)
        write_json(dest,result)
        if item['status']=='COMPLETED':break
        failure=item['failure']
        if index or not failure.startswith(('InvalidStructuredOutput','SchemaMismatch','IncompleteModelOutput')):break
        context=deepcopy(case['context']);context['previous_attempt_feedback']={'failure':failure,'instruction':'仅恢复符合原 schema 的完整 JSON 输出，仍按原始材料和规则判断。'}
    result.update(completed=now(),status=result['attempts'][-1]['status'])
    write_json(dest,result)
    return result


def run():
    if (OUT/'assessment.json').exists():raise Rejected('ComparisonAlreadyClosed')
    frozen=initialize();verify(frozen)
    for index,case in enumerate(frozen['spec']['cases']):
        for arm in (('disabled','high') if index%2==0 else ('high','disabled')):
            result=run_case(case,arm);verify(frozen)
            print(json.dumps({'case':case['id'],'arm':arm,'status':result['status'],'label_matched':result['attempts'][-1].get('label_matched')},ensure_ascii=False),flush=True)
            failure=result['attempts'][-1].get('failure','')
            if any(term in failure for term in ('Transport','ProviderHTTP','Budget','Persistence')):raise Rejected('InspectResourceOrNetworkPause:'+failure)
    write_json(OUT/'execution.json',{'created':now(),'status':'MEASURED','units':32,'changed_sources_during_execution':[],
                                    'budget':read(BUDGET),'formal_calls':0,'assessment':'PENDING'})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','run'));args=parser.parse_args()
    if args.stage=='prepare':prepare()
    else:run()
