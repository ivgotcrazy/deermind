"""Fixed X1/X2 real-Policy composition campaign, without extra scoring or retries."""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter, ModelFailure, http_transport, load_config
from foundation.records import json_value
from foundation.runtime import ContractError
from foundation.security import AccessDenied
from foundation.composition_cases import CompositionWorld, run_composition
from run_foundation import manifest
from run_policy_validation import load_design as load_policy
from run_semantic_stability import write_summary

ROOT=Path(__file__).resolve().parent


def load_design():
    fixture=json.loads((ROOT/'fixtures/composition-x1-x2-v1.json').read_text(encoding='utf-8'))
    policy,definition=load_policy()
    if sha256((ROOT/fixture['policy_protocol_path']).read_bytes()).hexdigest()!=fixture['policy_protocol_sha256']:
        raise ValueError('FrozenPolicyProtocolChanged')
    return fixture,policy,definition


def execute_branch(base,e,branch,repetition,config,transport=http_transport):
    w=base.branch(e)
    e.capture(w.h,'branch_initial')
    injection={'calls':0}
    def hook(url,key,wire,timeout):
        if not injection['calls'] and wire.get('tool_choice',{}).get('function',{}).get('name')=='submit_policy':
            injection['calls']+=1
            w.runtime.execution('PolicyInFlight',w.context.subject,{'turn_ref':json_value(w.turn),
                'context_id':w.context.identity,'model_call':adapter.records[-1]['execution_id']})
            if branch != 'X2-revoke':w.queue_next()
            if branch == 'X1-correction':w.external_correction()
            else:w.activate_v2()
        return transport(url,key,wire,timeout)
    adapter=DeepSeekAdapter(config,hook)
    row={'branch':branch,'repetition':repetition,'result':'NON_SUCCESS','coverage':'INCOMPLETE'}
    try:
        row.update(run_composition(w,branch,adapter,injection))
    except (ModelFailure,ContractError,AccessDenied) as exc:
        row.update(failure_type=type(exc).__name__,reason=str(exc))
    finally:
        for record in adapter.records:e.emit('model_execution',branch=branch,repetition=repetition,**record)
        e.capture(w.h,'branch_final')
        row.update(checks=len(e.checks),failed_checks=[c for c in e.checks if not c['passed']],model_calls=adapter.calls)
        if row['coverage']=='COMPLETE' and not row.get('failure_type') and not row['failed_checks']:
            row['result']='PASS'
        e.emit('branch_result',**row)
    return row


def summarize(rows,fixture,stop=None):
    return {'status':'PASS' if len(rows)==fixture['planned_branch_runs'] and all(r['result']=='PASS' for r in rows) else 'NON_SUCCESS',
        'planned_runs':fixture['planned_branch_runs'],'completed_runs':len(rows),'not_run':fixture['planned_branch_runs']-len(rows),
        'matched_runs':sum(r['result']=='PASS' for r in rows),'model_calls':sum(r['model_calls'] for r in rows),
        'max_model_calls':fixture['max_model_calls'],'stop_reason':stop,'runs':rows,
        'composition_assessment':'PENDING_EVIDENCE_REVIEW','gate_E':'OPEN','gate_F':'OPEN','automatic_additional_batches':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true');args=parser.parse_args(argv)
    fixture,policy,definition=load_design();repo=ROOT.parents[1]
    config=replace(load_config(repo),base_url=definition['provider_endpoint'],max_calls=fixture['max_model_calls'],
        max_output_tokens=fixture['max_output_tokens'],timeout_seconds=fixture['timeout_seconds'])
    directory=ROOT/'runs/composition-x1-x2-v1'
    ready=bool(config.api_key) and not directory.exists()
    if not args.run:
        print(json.dumps({'ready':ready,'already_reserved':directory.exists(),'network_calls':0,
            'model_config':config.public(),'branch_runs':fixture['planned_branch_runs'],'branch_limits':fixture['branch_call_limits']},indent=2));return 0 if ready else 2
    if not ready:print('Not started: missing key or fixed campaign already reserved.');return 2
    directory.mkdir(exist_ok=False)
    frozen=manifest(repo)
    design='src/spike/reports/composition-x1-x2-design-20261004.md'
    frozen['content_sha256'][design]=sha256((repo/design).read_bytes()).hexdigest()
    frozen.update(fixture=fixture,model_config=config.public(),scope=fixture['scope'],cases=['X1','X2'],repetitions=5)
    (directory/'manifest.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    e=EvidenceRecorder(directory/'baseline.jsonl')
    try:
        base=CompositionWorld(e,definition,policy)
        e.capture(base.h,'shared_initial_snapshot')
    finally:e.close()
    rows=[];stop=None
    for repetition in range(1,fixture['repetitions']+1):
        for branch in fixture['branches']:
            if stop:break
            if any(sha256((repo/p).read_bytes()).hexdigest()!=h for p,h in frozen['content_sha256'].items()):
                stop='FrozenInputsChanged';break
            e=EvidenceRecorder(directory/f'{repetition}-{branch}.jsonl')
            try:
                row=execute_branch(base,e,branch,repetition,replace(config,max_calls=fixture['branch_call_limits'][branch]))
            finally:e.close()
            rows.append(row)
            if row['failed_checks']:stop='InvariantCheckFailed'
            elif row.get('reason') in ('ProviderHTTPError:400','ProviderHTTPError:401','ProviderHTTPError:403','ProviderHTTPError:404','ProviderHTTPError:422'):stop=row['reason']
            elif len(rows)>=3 and all(r.get('failure_type') for r in rows[-3:]):stop='ConsecutiveProtocolOrRuntimeFailures'
            summary=summarize(rows,fixture,stop);write_summary(directory,summary)
            print(json.dumps({k:v for k,v in summary.items() if k!='runs'}),flush=True)
    summary=summarize(rows,fixture,stop);write_summary(directory,summary)
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
