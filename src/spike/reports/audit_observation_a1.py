"""Offline evidence integrity, excluding any automatic semantic adjudication."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]


def audit():
    directory=ROOT/'runs/observation-a1-v1'
    frozen=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    checks=[];calls=[];raw_checks=[];records=[];descriptions=[]
    def check(name,actual,expected):checks.append({'name':name,'actual':actual,'expected':expected,'passed':actual==expected})
    for p,h in frozen['content_sha256'].items():check('frozen:'+p,sha256((REPO/p).read_bytes()).hexdigest(),h)
    for row in summary['runs']:
        path=directory/f"{row['repetition']}-{row['variant']}.jsonl"
        events=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        model=[e for e in events if e['kind']=='model_execution'];calls+=model
        raw_checks.extend(e for e in events if e['kind']=='check')
        context=next(e['context'] for e in events if e['kind']=='A1_context')
        check(path.name+': context kinds',[i['record']['kind'] for i in context['items']],['LearnerWorkSubmitted','ObservationSemantics'])
        check(path.name+': three forbidden records excluded',len(context['excluded']),3)
        for event in events:
            if event['kind']=='A1_review':check(path.name+': real review',event['review']['fixture'],False)
            if event['kind']=='A1_candidate':descriptions.append({'file':path.name,'payload':json.loads(event['candidate']['record']['payload_json'])})
        final=next(e for e in reversed(events) if e['kind']=='snapshot')
        records.extend(final['records'])
        commits=[r for r in final['records'] if r['kind']=='Observation' and r['ref']['space']=='derived']
        check(path.name+': formal Observation only on committed result',len(commits),int(row['commit_status']=='Committed'))
        for record in commits:
            check(path.name+': forbidden history absent from dependencies',any(d['target']['identity'] in ('B-old','A-old','P-old') for d in record['dependencies']),False)
        check(path.name+': exact local call count',len(model),row['model_calls'])
    check('raw calls agree with summary',len(calls),summary['model_calls'])
    check('raw checks agree with summary',len(raw_checks),summary['checks'])
    check('raw invariants passed',all(c['passed'] for c in raw_checks),True)
    check('budget respected',len(calls)<=frozen['fixture']['max_model_calls'],True)
    check('unique provider execution ids',len({c['execution_id'] for c in calls}),len(calls))
    return {'status':'PASS' if all(c['passed'] for c in checks) else 'FAIL','frozen_inputs_verified':len(frozen['content_sha256']),
        'model_calls':len(calls),'call_statuses':dict(Counter(c['status'] for c in calls)),'raw_invariant_checks':len(raw_checks),
        'formal_observations':sum(r['kind']=='Observation' and r['ref']['space']=='derived' for r in records),
        'checks':checks,'candidates_for_content_review':descriptions,
        'note':'Mechanical evidence audit; content usefulness and AA-A01 result require separate review.'}


if __name__=='__main__':
    result=audit()
    (ROOT/'reports/observation-a1-audit-20261005.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','candidates_for_content_review')},indent=2))
    raise SystemExit(0 if result['status']=='PASS' else 1)
