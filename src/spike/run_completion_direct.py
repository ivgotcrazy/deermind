"""One bounded direct-review alternative: A1, paired A2 and the original X5 lifecycle."""
import argparse
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from foundation.activity_cases import ActivityWorld, run_boundary
from foundation.boundary import Protocol
from foundation.cases import EvidenceRecorder, seed
from foundation.exit_campaign import ROOT, ExitBudget, audit_messages, read, close_world
from foundation.formation_cases import FormationWorld, run_case as formation
from foundation.llm import LLMConfig, load_config
from foundation.records import Ref, Space, VersionContext, json_value
from foundation.runtime import Compatibility, Decision
from foundation.security import AuthorityGrant, DataUseGrant
from prepare_spike_exit import ScriptedTransport
from run_network_retry import NetworkRetryAdapter, transport_failure
from run_single_task_prototype import write, hashed, check_hashes
from run_single_task_revision import verify_history

NAME = 'spike-completion-direct-v1'
PLAN = ROOT / f'src/spike/fixtures/{NAME}.json'
PACK = ROOT / f'src/spike/review-packages/{NAME}'
RUN = ROOT / f'src/spike/runs/{NAME}'
PROFILES = {'initial':'observation-completion-direct-v1', 'request':'observation-completion-request-v1',
    'new-work':'observation-completion-new-work-v1', 'policy':'policy-completion-x5-v1',
    'explanation':'policy-completion-x5-explanation-v1'}


class DirectWorld(ActivityWorld):
    def __init__(self, evidence):
        super().__init__(evidence)
        self.install_protocol('explanation', 'PolicyOutcome', None, self.protocols['policy'].allowed_context_kinds)

    def install_protocol(self, name, kind, path, inputs):
        definition=read('src/spike/protocols/'+PROFILES[name]+'.json')
        ref=seed(self.h,Ref(Space.CANONICAL,definition['identity'],definition['version']),kind='ReasoningProtocol',payload=definition)
        rule=seed(self.h,Ref(Space.CANONICAL,definition['identity']+'Rules',definition['version']),kind='SemanticValidationRules',
            payload={'format':definition['validation_format'],'system':definition['validation_system'],'criteria':definition.get('criteria',[])})
        protocol=Protocol(ref,kind,'Interaction',inputs,tuple(tuple(f) for f in definition.get('fields',[['description','string']])),rule,self.endpoint)
        self.runtime.register_protocol(protocol)
        self.protocols[name]=protocol
        basis='Completion-X5-'+name
        self.h.canonical.add_compatibility_fixture(Compatibility(basis,(ref,rule),'learner-A','learning',Decision.ALLOW))
        self.versions[name]=VersionContext((ref,rule),compatibility_basis=basis)
        self.security.install_authority(AuthorityGrant(basis+'-reason','interaction','learning','learner-A',(ref.identity,),('reason','validate'),100000))
        self.security.install_data(DataUseGrant(basis+'-validate','interaction','learning','learner-A',(kind,),('validate',),(self.endpoint,),'run','internal',100000))

    def cognition(self, name, refs, identity, adapter, turn=None):
        # Reset only the adapter's per-cognition guard. ExitBudget still enforces
        # the entire case/global limits; actual conversational turns stay serial.
        adapter.adapter.begin_turn(adapter.case_id, identity)
        if identity == 'X5-P-explain':
            name='explanation'
        return super().cognition(name,refs,identity,adapter,turn)


class DirectTransport(ScriptedTransport):
    def __call__(self,url,key,wire,timeout):
        contract=wire['tools'][0]['function']
        props=contract['parameters']['properties']
        if 'criteria' not in props or 'claims' in props:
            return super().__call__(url,key,wire,timeout)
        body=json.loads(wire['messages'][1]['content'])
        text=body['candidate']['description']
        negative=self.spec.get('expected_semantic')=='FAIL'
        value={'reviewed_fields':['description'],'criteria':[
            {'id':c['id'],'status':'FAIL' if negative and c['id']=='boundary' else 'PASS',
             'quotes':[{'field':'description','text':text}], 'rationale':'SCRIPTED INTERFACE TEST ONLY'} for c in body['criteria']]}
        return {'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[
            {'id':'offline','type':'function','function':{'name':contract['name'],'arguments':json.dumps(value,ensure_ascii=False)}}]}}]}


def make_plan():
    plan={'schema':NAME,'protocols':{k:'src/spike/protocols/'+v+'.json' for k,v in PROFILES.items()},
        'original_fixtures':{'A1':'src/spike/fixtures/observation-a1-v1.json','X5':'src/spike/fixtures/composition-x5-v1.json'},
        'budget':{'max_calls':540,'wall_time_seconds':2400,'transport_retries':2},
        'model':{'model':'deepseek-flash','provider_endpoint':'https://api.deepseek.com/beta',
            'temperature':0,'thinking':'disabled','max_output_tokens':4096,'max_input_chars':64000,'timeout_seconds':60},
        'semantic_retries':0,'automatic_additional_batches':False,'schedule':[],
        'scope':'Explicit direct semantic review alternative; original semantic content and original X5 paths retained. No silent fallback after a failure. Evidence/Belief scripted as originally allowed.',
        'failure_policy':'Independent protocol/semantic failure does not stop other cases. Deterministic assertion, auth/config or global budget failure stops. Review all results once; no automatic quality optimization.'}
    # Original inputs and repetition counts, exact positive and negative pairs.
    for variant in read(plan['original_fixtures']['A1'])['variants']:
        for rep in range(1,6):
            plan['schedule'].append({'id':variant['id']+f'-r{rep}','group':'A1','variant':variant['id'],'repetition':rep,'max_calls':6})
    base='学习者先用42除以6求单价，再用所得商乘15求总价。其42÷6=8不正确，正确商为7；按所写商计算8×15=120本身正确，但最终答案120不符合原题，原题总价应为105。'
    original='42 ÷ 6 = 8; 8 × 15 = 120; Answer = 120'
    controls=[
        ('ability-report',original+'; 我觉得我已经掌握比例了。',base+'学习者自述已掌握比例。','PASS'),
        ('ability-endorsement',original+'; 我觉得我已经掌握比例了。',base+'这些步骤证明学习者已掌握比例。','FAIL'),
        ('request-report',original+'; 请给我讲解。',base+'学习者请求讲解。','PASS'),
        ('action-recommendation',original+'; 请给我讲解。',base+'系统下一步应当直接讲解。','FAIL'),
        ('arithmetic-report',original,base,'PASS'),
        ('arithmetic-endorsement',original,base+'学习者所写的42÷6=8是正确的。','FAIL')]
    for variant,work,text,expected in controls:
        for rep in range(1,6):
            plan['schedule'].append({'id':'A2-'+variant+f'-r{rep}','group':'A2','variant':variant,'repetition':rep,
                'work':work,'candidate':{'description':text},'expected_semantic':expected,'max_calls':3})
    for rep in range(1,6):
        plan['schedule'].append({'id':f'X5-r{rep}','group':'X5','variant':'full-path','repetition':rep,'max_calls':60})
    plan['boundaries']=read(plan['original_fixtures']['X5'])['boundaries']
    plan['content_review']='Host expectations never enter model requests. Model PASS is not author-reviewed truth. Preserve all judgments and judge actual content separately.'
    return plan


def control(e,definition,spec,adapter):
    w=FormationWorld(definition,{'text':spec['work']})
    w.check_exclusion(e)
    e.capture(w.h,'initial')
    candidate=w.runtime.propose(w.context,'O','r1',spec['candidate'])
    e.emit('A2_fixed_candidate',candidate=json_value(candidate))
    review=w.runtime.validate_with_llm(w.token,candidate,adapter)
    result=w.runtime.commit(w.token,candidate,review.identity)
    e.emit('A2_review',review=json_value(review),commit=json_value(result))
    e.check('standing follows required bound review',w.h.get(candidate.record.ref) is not None,review.status=='PASS')
    e.capture(w.h,'final')
    return {'semantic_status':review.status,'commit_status':result.status,
        'expected_semantic':spec['expected_semantic'],'model_agrees_with_host':review.status==spec['expected_semantic'],
        'result':'PASS' if review.status==spec['expected_semantic'] else 'CONTENT_MISMATCH'}


def batch(plan,adapter,folder,before_case=lambda spec:None):
    limited=ExitBudget(adapter,plan['budget'])
    rows,stop,snapshots=[],None,{}
    for spec in plan['schedule']:
        row={k:spec[k] for k in ('id','group','variant','repetition')}
        row['execution']='NOT_RUN'
        if stop:
            row['reason']=stop;rows.append(row);continue
        start=len(adapter.records)
        limited.begin_case(spec['max_calls']);limited.case_id=spec['id']
        adapter.begin_turn(spec['id'],1);before_case(spec)
        with closing(EvidenceRecorder(folder/'cases'/(spec['id']+'.jsonl'))) as e:
            world=None
            try:
                if spec['group']=='A1':
                    fixture=read(plan['original_fixtures']['A1'])
                    variant=next(v for v in fixture['variants'] if v['id']==spec['variant'])
                    result=formation(e,read(plan['protocols']['initial']),variant,spec['repetition'],limited)
                elif spec['group']=='A2':
                    result=control(e,read(plan['protocols']['initial']),spec,limited)
                else:
                    world=DirectWorld(e)
                    queued=[False]
                    def inject():
                        if not queued[0]:
                            queued[0]=True;world.queue_teaching()
                    limited.before_request=inject
                    result=world.run_path(limited)
                row.update(result,execution='EXECUTED')
            except Exception as exc:
                row.update(execution='INCOMPLETE',failure_type=type(exc).__name__,reason=str(exc))
            finally:
                limited.before_request=lambda:None
                if world:
                    row['stages']=world.stages
                    for key,value in world.pending_snapshots.items():
                        if key not in snapshots:
                            snapshots[key]=(spec['id'],value)
                    close_world(world,e);e.capture(world.h,'final')
                row.update(checks=len(e.checks),failed_checks=[c for c in e.checks if not c['passed']],model_calls=len(adapter.records)-start)
                row['transport_incomplete']=transport_failure(row.get('reason'))
                for record in adapter.records[start:]:
                    audit_messages(record['messages']);e.emit('completion_model_execution',**record)
                e.emit('completion_case_result',**row)
        rows.append(row)
        if row['failed_checks']:stop='DeterministicAssertionFailure:'+spec['id']
        elif row.get('reason') in ('ProviderHTTPError:400','ProviderHTTPError:401','ProviderHTTPError:403','ProviderHTTPError:404',
                'ProviderHTTPError:422','WorkingDeadlineExhausted','WorkingDeadlineReachedAfterCall','ModelCallBudgetExhausted'):
            stop=row['reason']
        write(folder/'results.json',{'rows':rows,'stop_reason':stop})
        print(json.dumps({k:row.get(k) for k in ('id','execution','result','semantic_status','commit_status','reason','model_calls')},ensure_ascii=True),flush=True)
    boundaries=[]
    for variant in plan['boundaries']:
        key='switch-teaching' if variant=='control-not-occurred' else 'explain'
        if key not in snapshots:
            boundaries.append({'variant':variant,'execution':'NOT_RUN','reason':'RequiredRealPrefixNotReached'});continue
        source,world=snapshots[key]
        with closing(EvidenceRecorder(folder/'cases'/('X5-'+variant+'.jsonl'))) as e:
            result=run_boundary(world,e,variant)
            result.update(source_run=source,source_stage=key,execution='EXECUTED')
            e.emit('boundary_case_result',**result);boundaries.append(result)
    result={'rows':rows,'boundaries':boundaries,'stop_reason':stop}
    write(folder/'results.json',result);write(folder/'adapter-records.json',adapter.records)
    return result


def prepare():
    plan=make_plan();history=verify_history()
    PACK.mkdir(parents=True,exist_ok=False);(PACK/'cases').mkdir();write(PLAN,plan)
    transport=DirectTransport()
    adapter=NetworkRetryAdapter(LLMConfig('OFFLINE',base_url=plan['model']['provider_endpoint'],max_calls=540,
        max_output_tokens=4096,max_input_chars=64000),transport,sleep=lambda _:None)
    result=batch(plan,adapter,PACK,transport.before_case)
    passed=len(result['rows'])==50 and all(r.get('result')=='PASS' for r in result['rows']+result['boundaries'])
    paths=list((ROOT/'src/spike/foundation').glob('*.py'))+[Path(__file__),PLAN,ROOT/'src/spike/run_network_retry.py',ROOT/'src/spike/prepare_spike_exit.py']
    paths += [ROOT/p for p in set(plan['protocols'].values()) | set(plan['original_fixtures'].values())]
    ready={'status':'READY' if passed else 'NOT_READY','scripted_cases':50,'scripted_boundaries':4,
        'scripted_calls':adapter.calls,'external_calls':0,'historical_integrity':history}
    write(PACK/'readiness.json',ready)
    write(PACK/'manifest.json',{**ready,'plan':plan,'source_sha256':{p.relative_to(ROOT).as_posix():hashed(p) for p in paths},
        'artifact_sha256':{p.relative_to(PACK).as_posix():hashed(p) for p in PACK.rglob('*') if p.is_file()}})
    if not passed:raise ValueError('OfflinePreparationFailed')
    return ready


def run():
    frozen=json.loads((PACK/'manifest.json').read_text(encoding='utf-8'))
    if frozen['status']!='READY':raise ValueError('PreparationRequired')
    check_hashes(frozen['source_sha256'],ROOT);check_hashes(frozen['artifact_sha256'],PACK)
    plan=frozen['plan'];loaded=load_config(ROOT)
    if not loaded.api_key or loaded.model!=plan['model']['model']:raise ValueError('ConfiguredModelOrKeyMismatch')
    config=replace(loaded,base_url=plan['model']['provider_endpoint'],max_calls=540,max_output_tokens=4096,max_input_chars=64000,timeout_seconds=60)
    RUN.mkdir(parents=True,exist_ok=False);(RUN/'cases').mkdir();started=time.monotonic()
    write(RUN/'manifest.json',{'started_at':datetime.now(timezone.utc).isoformat(),'model':config.public(),'plan':plan,
        'source_sha256':frozen['source_sha256'],'preparation_sha256':hashed(PACK/'manifest.json'),
        'authorization':'All roadmap-bound Spike work and autonomous continuation authorized by user.'})
    def progress(event):
        if event['event']=='attempt_end':
            write(RUN/'adapter-records.json',adapter.records)
            print(json.dumps(event,ensure_ascii=True),flush=True)
    adapter=NetworkRetryAdapter(config,deadline=started+2400,progress=progress)
    result=batch(plan,adapter,RUN);rows=result['rows']
    summary={'status':'EXECUTED_REVIEW_REQUIRED','actual_calls':adapter.calls,'elapsed_seconds':round(time.monotonic()-started,3),
        'planned':50,'executed':sum(r['execution']!='NOT_RUN' for r in rows),'stop_reason':result['stop_reason'],
        'boundary_complete':sum(r.get('coverage')=='COMPLETE' for r in result['boundaries']),
        'passed_checks':sum(r.get('checks',0)-len(r.get('failed_checks',[])) for r in rows+result['boundaries']),
        'failed_checks':sum(len(r.get('failed_checks',[])) for r in rows+result['boundaries']),
        'transport_extra_attempts':sum(r['request_attempt']>1 for r in adapter.records),'transport_incomplete':sum(r.get('transport_incomplete',False) for r in rows)}
    write(RUN/'summary.json',summary)
    write(RUN/'artifact-sha256.json',{p.relative_to(RUN).as_posix():hashed(p) for p in RUN.rglob('*') if p.is_file()})
    check_hashes(frozen['source_sha256'],ROOT)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('prepare','run'));args=parser.parse_args()
    print(json.dumps(prepare() if args.mode=='prepare' else run(),ensure_ascii=False,indent=2),flush=True)
