"""One fixed A1 batch; preflight is offline, --run reserves 15 attempts."""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from foundation.cases import EvidenceRecorder
from foundation.formation_cases import run_case
from foundation.llm import DeepSeekAdapter, load_config
from foundation.protocol_preflight import check_observation_contract
from run_foundation import manifest

ROOT=Path(__file__).resolve().parent
PLAN=ROOT/'reports/observation-a1-design-20261005.md'


def load_design():
    fixture=json.loads((ROOT/'fixtures/observation-a1-v1.json').read_text(encoding='utf-8'))
    data=(ROOT/fixture['protocol_path']).read_bytes()
    if sha256(data).hexdigest()!=fixture['protocol_sha256']:raise ValueError('FrozenProtocolChanged')
    definition=json.loads(data)
    check_observation_contract(definition)
    return fixture,definition


def summarize(rows,fixture,stop=None):
    passed=len(rows)==fixture['planned_runs'] and all(r['result']=='PASS' for r in rows)
    return {'status':'PASS' if passed else 'NON_SUCCESS','assumption_assessment':'PENDING_CONTENT_REVIEW',
        'planned_runs':fixture['planned_runs'],'completed_runs':len(rows),'matched_runs':sum(r['result']=='PASS' for r in rows),
        'not_run':fixture['planned_runs']-len(rows),'model_calls':sum(r['model_calls'] for r in rows),
        'max_model_calls':fixture['max_model_calls'],'checks':sum(r['checks'] for r in rows),
        'failed_checks':[c for r in rows for c in r['failed_checks']],'runs':rows,'stop_reason':stop,
        'automatic_additional_batches':False,'gate_E':'OPEN','gate_F':'OPEN'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true');args=parser.parse_args(argv)
    fixture,definition=load_design();repo=ROOT.parents[1]
    config=replace(load_config(repo),base_url=definition['provider_endpoint'],max_calls=fixture['max_calls_per_run'],
        max_output_tokens=fixture['max_output_tokens'],timeout_seconds=fixture['timeout_seconds'])
    directory=ROOT/'runs/observation-a1-v1'
    ready=bool(config.api_key) and not directory.exists() and PLAN.exists()
    if not args.run:
        print(json.dumps({'ready':ready,'already_reserved':directory.exists(),'network_calls':0,'model_config':config.public(),
            'attempts':fixture['planned_runs'],'max_total_calls':fixture['max_model_calls'],'contract_preflight':check_observation_contract(definition)},indent=2));return 0 if ready else 2
    if not ready:print('Not started: key/plan missing or fixed campaign already reserved.');return 2
    directory.mkdir(exist_ok=False)
    frozen=manifest(repo)
    frozen['content_sha256'][PLAN.relative_to(repo).as_posix()]=sha256(PLAN.read_bytes()).hexdigest()
    frozen.update(fixture=fixture,model_config=config.public(),cases=['A1'],repetitions=5,
        scope='A1 real belief-free formation and utility under one shared semantics/context/model configuration')
    (directory/'manifest.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[];stop=None
    for repetition in range(1,fixture['repetitions']+1):
        for variant in fixture['variants']:
            if stop:break
            if any(sha256((repo/p).read_bytes()).hexdigest()!=h for p,h in frozen['content_sha256'].items()):stop='FrozenInputsChanged';break
            e=EvidenceRecorder(directory/f"{repetition}-{variant['id']}.jsonl")
            try:row=run_case(e,definition,variant,repetition,DeepSeekAdapter(config))
            finally:e.close()
            rows.append(row)
            if row['failed_checks']:stop='InvariantCheckFailed'
            elif row.get('reason') in ('ProviderHTTPError:400','ProviderHTTPError:401','ProviderHTTPError:403','ProviderHTTPError:404','ProviderHTTPError:422'):stop=row['reason']
            elif len(rows)>=3 and all(r.get('failure_type') for r in rows[-3:]):stop='ConsecutiveProtocolOrRuntimeFailures'
            summary=summarize(rows,fixture,stop)
            (directory/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in summary.items() if k not in ('runs','failed_checks')}),flush=True)
    summary=summarize(rows,fixture,stop)
    (directory/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
