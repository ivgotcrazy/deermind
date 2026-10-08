"""Repair explicit X5 context omissions; keep prompts and action fixtures unchanged."""
import argparse
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from foundation.activity_cases import ActivityWorld, run_boundary
from foundation.boundary import Protocol
from foundation.cases import EvidenceRecorder, seed
from foundation.exit_campaign import ROOT, ExitBudget, audit_messages, read, close_world
from foundation.llm import LLMConfig, load_config
from foundation.records import Ref, Space, VersionContext, json_value
from foundation.runtime import Compatibility, Decision
from foundation.security import AuthorityGrant, DataUseGrant
from run_completion_direct import DirectWorld, DirectTransport, PROFILES
from run_network_retry import NetworkRetryAdapter, transport_failure
from run_single_task_prototype import write, hashed, check_hashes

NAME='spike-completion-x5-context-v2'
PLAN=ROOT/f'src/spike/fixtures/{NAME}.json'
PACK=ROOT/f'src/spike/review-packages/{NAME}'
RUN=ROOT/f'src/spike/runs/{NAME}'
PROFILES={**PROFILES,'policy':'policy-completion-x5-context-v2','explanation':'policy-completion-x5-explanation-context-v2'}


class ContextWorld(DirectWorld):
    def install_protocol(self,name,kind,path,inputs):
        definition=read('src/spike/protocols/'+PROFILES[name]+'.json')
        if kind=='PolicyOutcome':inputs=(*inputs,'LearnerWorkSubmitted')
        ref=seed(self.h,Ref(Space.CANONICAL,definition['identity'],definition['version']),kind='ReasoningProtocol',payload=definition)
        rule=seed(self.h,Ref(Space.CANONICAL,definition['identity']+'Rules',definition['version']),kind='SemanticValidationRules',
            payload={'format':definition['validation_format'],'system':definition['validation_system'],'criteria':definition.get('criteria',[])})
        protocol=Protocol(ref,kind,'Interaction',inputs,tuple(tuple(f) for f in definition.get('fields',[['description','string']])),rule,self.endpoint)
        self.runtime.register_protocol(protocol);self.protocols[name]=protocol
        basis='Completion-X5-context-'+name
        self.h.canonical.add_compatibility_fixture(Compatibility(basis,(ref,rule),'learner-A','learning',Decision.ALLOW))
        self.versions[name]=VersionContext((ref,rule),compatibility_basis=basis)
        self.security.install_authority(AuthorityGrant(basis+'-reason','interaction','learning','learner-A',(ref.identity,),('reason','validate'),100000))
        self.security.install_data(DataUseGrant(basis+'-validate','interaction','learning','learner-A',(kind,),('validate',),(self.endpoint,),'run','internal',100000))

    def cognition(self,name,refs,identity,adapter,turn=None):
        if identity=='X5-P-explain':refs=(*refs,self.work)
        if name=='policy' and hasattr(self,'explanation_occurrence'):
            refs=(*refs,self.explanation_occurrence)
        return super().cognition(name,refs,identity,adapter,turn)

    def context(self,name,refs):
        ctx=super().context(name,refs)
        actual={i.record.ref for i in ctx.items}
        if name=='explanation':
            self.e.check('ActionSemantic review context includes original learner work',self.work in actual,True)
        if name=='policy' and hasattr(self,'explanation_occurrence'):
            self.e.check('post-teaching Policy context includes actual previous disclosure',self.explanation_occurrence in actual,True)
        return ctx


def make_plan():
    return {'schema':NAME,'protocols':{k:'src/spike/protocols/'+v+'.json' for k,v in PROFILES.items()},
        'basis':'src/spike/runs/spike-completion-direct-v1',
        'reason':'Author audit found actual source absence: original work omitted from explanation Policy; prior explanation occurrence omitted from later Policy contexts. This is an explicit context-contract implementation repair, not a semantic prompt optimization.',
        'unchanged':['generation_system','validation_system','model','semantic_criteria','original_four_turn_X5_path','four_effect_boundaries','action_payloads','scripted_Evaluation'],
        'budget':{'max_calls':300,'wall_time_seconds':1200,'transport_retries':2},
        'model':{'model':'deepseek-flash','provider_endpoint':'https://api.deepseek.com/beta','temperature':0,'thinking':'disabled',
            'max_output_tokens':4096,'max_input_chars':64000,'timeout_seconds':60},
        'schedule':[{'id':f'X5-r{i}','repetition':i,'max_calls':60} for i in range(1,6)],
        'boundaries':read('src/spike/fixtures/composition-x5-v1.json')['boundaries'],
        'semantic_retries':0,'automatic_additional_batches':False}


def batch(plan,adapter,folder):
    limited=ExitBudget(adapter,plan['budget']);rows=[];snapshots={};stop=None
    for spec in plan['schedule']:
        row={**spec,'execution':'NOT_RUN'}
        if stop:row['reason']=stop;rows.append(row);continue
        limited.begin_case(spec['max_calls']);limited.case_id=spec['id'];start=len(adapter.records)
        with closing(EvidenceRecorder(folder/'cases'/(spec['id']+'.jsonl'))) as e:
            w=ContextWorld(e);queued=[False]
            def inject():
                if not queued[0]:queued[0]=True;w.queue_teaching()
            limited.before_request=inject
            try:row.update(w.run_path(limited),execution='EXECUTED')
            except Exception as exc:row.update(execution='INCOMPLETE',failure_type=type(exc).__name__,reason=str(exc))
            finally:
                limited.before_request=lambda:None
                for key,value in w.pending_snapshots.items():
                    if key not in snapshots:snapshots[key]=(spec['id'],value)
                row['stages']=w.stages;close_world(w,e);e.capture(w.h,'final')
                row.update(checks=len(e.checks),failed_checks=[c for c in e.checks if not c['passed']],model_calls=len(adapter.records)-start)
                row['transport_incomplete']=transport_failure(row.get('reason'))
                for record in adapter.records[start:]:audit_messages(record['messages']);e.emit('completion_model_execution',**record)
                e.emit('completion_case_result',**row)
        rows.append(row)
        if row['failed_checks']:stop='DeterministicAssertionFailure:'+spec['id']
        elif row.get('reason') in ('ProviderHTTPError:400','ProviderHTTPError:401','ProviderHTTPError:403','ProviderHTTPError:404',
                'ProviderHTTPError:422','WorkingDeadlineExhausted','WorkingDeadlineReachedAfterCall','ModelCallBudgetExhausted'):
            stop=row['reason']
        write(folder/'results.json',{'rows':rows,'stop_reason':stop})
        print(json.dumps({k:row.get(k) for k in ('id','execution','result','reason','model_calls')},ensure_ascii=True),flush=True)
    boundaries=[]
    for variant in plan['boundaries']:
        key='switch-teaching' if variant=='control-not-occurred' else 'explain'
        if key not in snapshots:boundaries.append({'variant':variant,'execution':'NOT_RUN','reason':'RequiredRealPrefixNotReached'});continue
        source,w=snapshots[key]
        with closing(EvidenceRecorder(folder/'cases'/('X5-'+variant+'.jsonl'))) as e:
            result=run_boundary(w,e,variant);result.update(source_run=source,source_stage=key,execution='EXECUTED')
            e.emit('boundary_case_result',**result);boundaries.append(result)
    result={'rows':rows,'boundaries':boundaries,'stop_reason':stop}
    write(folder/'results.json',result);write(folder/'adapter-records.json',adapter.records)
    return result


def prepare():
    plan=make_plan();PACK.mkdir(parents=True,exist_ok=False);(PACK/'cases').mkdir();write(PLAN,plan)
    adapter=NetworkRetryAdapter(LLMConfig('OFFLINE',base_url=plan['model']['provider_endpoint'],max_calls=300,
        max_output_tokens=4096,max_input_chars=64000),DirectTransport(),sleep=lambda _:None)
    result=batch(plan,adapter,PACK)
    passed=all(r.get('result')=='PASS' for r in result['rows']+result['boundaries'])
    paths=list((ROOT/'src/spike/foundation').glob('*.py'))+[Path(__file__),PLAN,ROOT/'src/spike/run_completion_direct.py',
        ROOT/'src/spike/run_network_retry.py',ROOT/'src/spike/prepare_spike_exit.py',ROOT/'src/spike/fixtures/composition-x5-v1.json']
    paths+=[ROOT/p for p in plan['protocols'].values()]
    ready={'status':'READY' if passed else 'NOT_READY','scripted_paths':5,'scripted_boundaries':4,'scripted_calls':adapter.calls,'external_calls':0}
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
    config=replace(loaded,base_url=plan['model']['provider_endpoint'],max_calls=300,max_output_tokens=4096,max_input_chars=64000,timeout_seconds=60)
    RUN.mkdir(parents=True,exist_ok=False);(RUN/'cases').mkdir();started=time.monotonic()
    write(RUN/'manifest.json',{'started_at':datetime.now(timezone.utc).isoformat(),'model':config.public(),'plan':plan,
        'source_sha256':frozen['source_sha256'],'preparation_sha256':hashed(PACK/'manifest.json'),
        'authorization':'User authorized all necessary Spike work, simple implementation repairs and autonomous continuation.'})
    def progress(event):
        if event['event']=='attempt_end':
            write(RUN/'adapter-records.json',adapter.records);print(json.dumps(event,ensure_ascii=True),flush=True)
    adapter=NetworkRetryAdapter(config,deadline=started+1200,progress=progress)
    result=batch(plan,adapter,RUN);rows=result['rows']+result['boundaries']
    summary={'status':'EXECUTED_REVIEW_REQUIRED','actual_calls':adapter.calls,'elapsed_seconds':round(time.monotonic()-started,3),
        'planned':5,'complete':sum(r.get('coverage')=='COMPLETE' for r in result['rows']),
        'boundary_complete':sum(r.get('coverage')=='COMPLETE' for r in result['boundaries']),'stop_reason':result['stop_reason'],
        'passed_checks':sum(r.get('checks',0)-len(r.get('failed_checks',[])) for r in rows),'failed_checks':sum(len(r.get('failed_checks',[])) for r in rows),
        'transport_extra_attempts':sum(r['request_attempt']>1 for r in adapter.records),'transport_incomplete':sum(r.get('transport_incomplete',False) for r in rows)}
    write(RUN/'summary.json',summary);write(RUN/'artifact-sha256.json',{p.relative_to(RUN).as_posix():hashed(p) for p in RUN.rglob('*') if p.is_file()})
    check_hashes(frozen['source_sha256'],ROOT)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('prepare','run'));args=parser.parse_args()
    print(json.dumps(prepare() if args.mode=='prepare' else run(),ensure_ascii=False,indent=2),flush=True)
