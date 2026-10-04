"""Fixed deterministic X3/X4 campaign; no external model calls."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from foundation.cases import EvidenceRecorder
from foundation.history_composition_cases import CASES
from run_foundation import manifest
from run_semantic_stability import write_summary

ROOT=Path(__file__).resolve().parent


def execute_case(name,e):
    row={'case_id':name,'result':'NON_SUCCESS','coverage':'INCOMPLETE'}
    try:row.update(CASES[name](e))
    except Exception as exc:
        row.update(failure_type=type(exc).__name__,reason=str(exc))
        e.emit('case_failure',**row)
    row.update(checks=len(e.checks),failed_checks=[c for c in e.checks if not c['passed']])
    if row['coverage']=='COMPLETE' and not row.get('failure_type') and not row['failed_checks']:row['result']='PASS'
    e.emit('case_result',**row)
    return row


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true');args=parser.parse_args(argv)
    fixture=json.loads((ROOT/'fixtures/composition-x3-x4-v1.json').read_text(encoding='utf-8'))
    directory=ROOT/'runs/composition-x3-x4-v1';repo=ROOT.parents[1]
    if not args.run:
        print(json.dumps({'ready':not directory.exists(),'cases':fixture['cases'],'model_calls':0}));return 0 if not directory.exists() else 2
    if directory.exists():print('Fixed campaign already reserved; no replacement run.');return 2
    directory.mkdir(exist_ok=False)
    frozen=manifest(repo);design='src/spike/reports/composition-x3-x4-design-20261004.md'
    frozen['content_sha256'][design]=sha256((repo/design).read_bytes()).hexdigest()
    frozen.update(fixture=fixture,cases=fixture['cases'],scope=fixture['scope'],model_calls=0)
    (directory/'manifest.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[];stop=None
    for name in fixture['cases']:
        if any(sha256((repo/p).read_bytes()).hexdigest()!=h for p,h in frozen['content_sha256'].items()):
            stop='FrozenInputsChanged';break
        e=EvidenceRecorder(directory/(name+'.jsonl'))
        try:row=execute_case(name,e)
        finally:e.close()
        rows.append(row)
        if row['result']!='PASS':stop='CaseIncompleteOrInvariantFailed'
        write_summary(directory,{'cases':rows,'model_calls':0,'stop_reason':stop,'composition_assessment':'PENDING_EVIDENCE_REVIEW'})
        print(json.dumps({k:v for k,v in row.items() if k!='failed_checks'}),flush=True)
        if stop:break
    summary={'status':'PASS' if len(rows)==len(fixture['cases']) and all(r['result']=='PASS' for r in rows) else 'NON_SUCCESS',
        'cases':rows,'not_run':[c for c in fixture['cases'] if c not in {r['case_id'] for r in rows}],
        'model_calls':0,'stop_reason':stop,'composition_assessment':'PENDING_EVIDENCE_REVIEW',
        'automatic_additional_batches':False,'gate_E':'OPEN','gate_F':'OPEN'}
    write_summary(directory,summary)
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
