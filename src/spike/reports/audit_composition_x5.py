"""Read-only X5 evidence checks; no model calls or experiment retries."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]


def audit():
    directory=ROOT/'runs/composition-x5-v1'
    frozen=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    checks=[];calls=[];stages=[];counts=Counter();raw_checks=[];ancestry=[]
    def check(name,actual,expected):checks.append({'name':name,'actual':actual,'expected':expected,'passed':actual==expected})
    for p,h in frozen['content_sha256'].items():check('frozen:'+p,sha256((REPO/p).read_bytes()).hexdigest(),h)
    for path in sorted(directory.glob('*.jsonl')):
        events=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        model=[e for e in events if e['kind']=='model_execution'];calls+=model
        raw_checks.extend(e for e in events if e['kind']=='check')
        ancestry.extend(e for e in events if e['kind']=='real_snapshot_ancestry')
        for event in events:
            if event['kind']=='X5_cognition':
                stages.append({'file':path.name,'stage':event['stage'],'semantic_status':event['review']['status'],
                    'commit_status':event['outcome']['status'],'reason':event['outcome']['reason'],
                    'payload':json.loads(event['candidate']['record']['payload_json'])})
                check(path.name+': real semantic review '+event['stage'],event['review']['fixture'],False)
                check(path.name+': model provenance '+event['stage'],event['review']['model_ref'],frozen['model_config']['model'])
        final=next((e for e in reversed(events) if e['kind']=='snapshot'),None)
        if final:
            for record in final['records']:
                counts[record['kind']]+=1
            check(path.name+': history has no activity correction',
                  any(r['corrects'] for r in final['records'] if r['kind']=='ActivityTransitionOccurred'),False)
            transitions={r['ref']['identity']:json.loads(r['payload_json']) for r in final['records'] if r['kind']=='ActivityTransitionOccurred'}
            for payload in transitions.values():
                check(path.name+': Control acknowledgement retained',any(r['ref']==payload['acknowledgement_ref'] and r['kind']=='ControlAcknowledgement' for r in final['records']),True)
    check('raw model call count equals summary',len(calls),summary['model_calls'])
    check('within predeclared call budget',len(calls)<=frozen['fixture']['max_model_calls'],True)
    check('raw invariant check count equals summary',len(raw_checks),summary['checks'])
    check('all invariant checks passed',all(c['passed'] for c in raw_checks),True)
    check('no duplicate provider execution ids',len({c['execution_id'] for c in calls}),len(calls))
    for source in ancestry:
        events=[json.loads(line) for line in (directory/source['parent_file']).read_text(encoding='utf-8').splitlines()]
        check('actual stage ancestry '+source['stage'],any(e['kind']=='snapshot' and e['label']=='before-effect:'+source['stage'] for e in events),True)
    return {'status':'PASS' if all(c['passed'] for c in checks) else 'FAIL','checks':checks,
        'frozen_inputs_verified':len(frozen['content_sha256']),'raw_invariant_checks':len(raw_checks),
        'model_calls':len(calls),'call_statuses':dict(Counter(c.get('status','unknown') for c in calls)),
        'stage_results':stages,'snapshot_record_counts_including_shared_ancestry':dict(counts),
        'note':'Mechanical evidence audit is not a semantic quality verdict or full-path coverage.'}


if __name__=='__main__':
    result=audit()
    (ROOT/'reports/composition-x5-audit-20261005.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','stage_results','snapshot_record_counts_including_shared_ancestry')},indent=2))
    raise SystemExit(0 if result['status']=='PASS' else 1)
