"""One reserved, predeclared E1 real Policy campaign; never silently retry."""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter, load_config
from foundation.policy_cases import negative_fixture, run_policy_case
from run_foundation import manifest
from run_semantic_stability import write_summary

ROOT=Path(__file__).resolve().parent


def load_design():
    fixture=json.loads((ROOT/'fixtures/policy-e1-v1.json').read_text(encoding='utf-8'))
    data=(ROOT/fixture['protocol_path']).read_bytes()
    if sha256(data).hexdigest()!=fixture['protocol_sha256']:
        raise ValueError('FrozenProtocolHashMismatch')
    return fixture,json.loads(data)


def summarize(results, fixture, calls, negative_passed, stop_reason=None):
    return {'status':'PASS' if len(results)==fixture['candidate_runs'] and all(r['result']=='PASS' for r in results) and negative_passed else 'NON_SUCCESS',
        'planned_runs':fixture['candidate_runs'],'completed_runs':len(results),'not_run':fixture['candidate_runs']-len(results),
        'matched_runs':sum(r['result']=='PASS' for r in results),'model_calls':calls,'max_model_calls':fixture['max_model_calls'],
        'protocol_or_runtime_failures':sum(bool(r.get('failure_type')) for r in results),
        'illegal_commits':sum(r['illegal_commit'] for r in results),'forbidden_effects':sum(r['forbidden_effect'] for r in results),
        'negative_fixture_passed':negative_passed,'stop_reason':stop_reason,'runs':results,
        'assumption_assessment':'PENDING_EVIDENCE_REVIEW','gate_E':'OPEN','gate_F':'OPEN','automatic_additional_batches':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true');args=parser.parse_args(argv)
    fixture,definition=load_design();repo=ROOT.parents[1]
    config=replace(load_config(repo),base_url=definition['provider_endpoint'],max_calls=fixture['max_model_calls'],
        max_output_tokens=fixture['max_output_tokens'],timeout_seconds=fixture['timeout_seconds'])
    directory=ROOT/'runs/policy-e1-v1'
    ready=bool(config.api_key) and not directory.exists()
    if not args.run:
        print(json.dumps({'ready':ready,'already_reserved':directory.exists(),'network_calls':0,'model_config':config.public(),
            'candidate_runs':fixture['candidate_runs'],'protocol_sha256':fixture['protocol_sha256']},indent=2));return 0 if ready else 2
    if not ready:
        print('Not started: key absent or fixed campaign already reserved. No automatic retry.');return 2
    directory.mkdir(exist_ok=False)
    frozen=manifest(repo);frozen.update(fixture=fixture,model_config=config.public(),scope=fixture['scope'],cases=['E1'],repetitions=5)
    (directory/'manifest.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    e=EvidenceRecorder(directory/'negative.jsonl')
    try:negative=negative_fixture(e,definition,fixture)
    finally:e.close()
    results=[];adapter=DeepSeekAdapter(config);stop=None
    e=EvidenceRecorder(directory/'evidence.jsonl')
    try:
        e.emit('predeclared_design',fixture=fixture,protocol=definition,config=config.public())
        if not negative:stop='NegativeAdmissionFixtureFailed'
        for repetition in range(1,fixture['repetitions']+1):
            for variant in fixture['variants']:
                if stop:break
                if any(sha256((repo/p).read_bytes()).hexdigest()!=h for p,h in frozen['content_sha256'].items()):
                    stop='FrozenInputsChanged';break
                row=run_policy_case(e,definition,fixture,variant,repetition,adapter);results.append(row)
                if row['illegal_commit'] or row['forbidden_effect']:stop='IllegalCommitOrForbiddenEffect'
                elif row.get('reason') in ('ProviderHTTPError:400','ProviderHTTPError:401','ProviderHTTPError:403','ProviderHTTPError:404','ProviderHTTPError:422'):stop=row['reason']
                elif len(results)>=3 and all(r.get('failure_type') for r in results[-3:]):stop='ConsecutiveProtocolOrRuntimeFailures'
                summary=summarize(results,fixture,adapter.calls,negative,stop);write_summary(directory,summary)
                print(json.dumps({k:v for k,v in summary.items() if k!='runs'}),flush=True)
        summary=summarize(results,fixture,adapter.calls,negative,stop);write_summary(directory,summary)
    finally:e.close()
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
