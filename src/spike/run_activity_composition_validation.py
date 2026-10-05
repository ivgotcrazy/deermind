"""X5 preflight by default; one reserved real-model campaign with no retries."""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from foundation.activity_cases import ActivityWorld, PathIncomplete, run_boundary
from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter, ModelFailure, http_transport, load_config
from foundation.runtime import ContractError
from foundation.security import AccessDenied
from run_foundation import manifest

ROOT=Path(__file__).resolve().parent
PLAN=ROOT/'reports/composition-x5-design-20261005.md'


def load_design():
    f=json.loads((ROOT/'fixtures/composition-x5-v1.json').read_text(encoding='utf-8'))
    for p,h in f['protocol_sha256'].items():
        if sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise ValueError('FrozenProtocolChanged:'+p)
    return f


def execute_path(e, repetition, config, transport=http_transport, world_type=ActivityWorld):
    w=world_type(e)
    e.capture(w.h,'path_initial')
    injected=False
    def hook(url,key,wire,timeout):
        nonlocal injected
        if not injected:
            injected=True
            w.queue_teaching()
        return transport(url,key,wire,timeout)
    adapter=DeepSeekAdapter(config,hook)
    row={'repetition':repetition,'result':'NON_SUCCESS','coverage':'INCOMPLETE'}
    try:
        row.update(w.run_path(adapter))
    except (ModelFailure,ContractError,AccessDenied) as exc:
        row.update(failure_type=type(exc).__name__,reason=str(exc),protocol_or_runtime_failure=not isinstance(exc,PathIncomplete))
    finally:
        for record in adapter.records:e.emit('model_execution',repetition=repetition,**record)
        e.capture(w.h,'path_final')
        row.update(model_calls=adapter.calls,checks=len(e.checks),failed_checks=[c for c in e.checks if not c['passed']],
                   stages=w.stages,snapshots_reached=list(w.pending_snapshots))
        if row['failed_checks']:row['result']='FAIL'
        e.emit('path_result',**row)
    return row,w.pending_snapshots


def summarize(rows, boundaries, fixture, stop=None):
    passed=len(rows)==fixture['repetitions'] and all(r['result']=='PASS' for r in rows) and len(boundaries)==4 and all(r['result']=='PASS' for r in boundaries)
    return {'status':'PASS' if passed else 'NON_SUCCESS','composition_result':'PASS' if passed else 'INCONCLUSIVE',
        'planned_runs':fixture['repetitions'],'completed_runs':len(rows),'complete_paths':sum(r['coverage']=='COMPLETE' for r in rows),
        'model_calls':sum(r['model_calls'] for r in rows),'max_model_calls':fixture['max_model_calls'],
        'checks':sum(r['checks'] for r in rows+boundaries),'failed_checks':[c for r in rows+boundaries for c in r.get('failed_checks',[])],
        'stop_reason':stop,'runs':rows,'boundaries':boundaries,'automatic_additional_batches':False,'gate_E':'OPEN','gate_F':'OPEN'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true');args=parser.parse_args(argv)
    f=load_design();repo=ROOT.parents[1]
    config=replace(load_config(repo),base_url='https://api.deepseek.com/beta',max_calls=f['max_calls_per_run'],
                   max_output_tokens=f['max_output_tokens'],timeout_seconds=f['timeout_seconds'])
    directory=ROOT/'runs/composition-x5-v1'
    ready=bool(config.api_key) and not directory.exists() and PLAN.exists()
    if not args.run:
        print(json.dumps({'ready':ready,'already_reserved':directory.exists(),'network_calls':0,'model_config':config.public(),
                          'attempts':f['repetitions'],'total_max_calls':f['max_model_calls']},indent=2));return 0 if ready else 2
    if not ready:print('Not started: missing key, plan, or fixed campaign already reserved.');return 2
    directory.mkdir(exist_ok=False)
    frozen=manifest(repo)
    frozen['content_sha256'][PLAN.relative_to(repo).as_posix()]=sha256(PLAN.read_bytes()).hexdigest()
    frozen.update(fixture=f,model_config=config.public(),scope='X5 real Observation/Policy, scripted Evaluation, mock control/display',cases=['X5'],repetitions=5)
    (directory/'manifest.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[];boundaries=[];sources={};stop=None
    def write():
        summary=summarize(rows,boundaries,f,stop)
        (directory/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in summary.items() if k not in ('runs','boundaries','failed_checks')}),flush=True)
        return summary
    for n in range(1,f['repetitions']+1):
        if any(sha256((repo/p).read_bytes()).hexdigest()!=h for p,h in frozen['content_sha256'].items()):stop='FrozenInputsChanged';break
        e=EvidenceRecorder(directory/f'{n}-path.jsonl')
        try:row,snapshots=execute_path(e,n,config)
        finally:e.close()
        rows.append(row)
        for stage,world in snapshots.items():
            if stage not in sources:sources[stage]=(n,world)
        if row['failed_checks']:stop='InvariantCheckFailed'
        elif row.get('reason') in ('ProviderHTTPError:400','ProviderHTTPError:401','ProviderHTTPError:403','ProviderHTTPError:404','ProviderHTTPError:422'):stop=row['reason']
        elif len(rows)>=3 and all(r.get('protocol_or_runtime_failure') for r in rows[-3:]):stop='ConsecutiveProtocolOrRuntimeFailures'
        write()
        if stop:break
    for variant in f['boundaries']:
        stage='switch-teaching' if variant=='control-not-occurred' else 'explain'
        if stage not in sources:
            boundaries.append({'variant':variant,'coverage':'NOT_RUN','result':'INCONCLUSIVE','reason':'RequiredRealStageNotReached','checks':0,'model_calls':0})
            continue
        n,w=sources[stage]
        e=EvidenceRecorder(directory/(variant+'.jsonl'))
        try:
            e.emit('real_snapshot_ancestry',parent_file=f'{n}-path.jsonl',stage=stage,model_calls=0)
            row=run_boundary(w,e,variant);row['parent_repetition']=n
        finally:e.close()
        boundaries.append(row)
    summary=write()
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
