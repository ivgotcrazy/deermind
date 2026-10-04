"""Frozen-run X1/X2 evidence and temporal audit. No new model calls."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
RUN=ROOT/'runs/composition-x1-x2-v1'


def sha(p):return sha256(p.read_bytes()).hexdigest()
def digest(v):return sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def lines(p):return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()]
def key(ref):return tuple(ref[k] for k in ('space','identity','revision'))
def payload(record):return json.loads(record['payload_json'])


def audit():
    manifest=json.loads((RUN/'manifest.json').read_text(encoding='utf-8'))
    summary=json.loads((RUN/'summary.json').read_text(encoding='utf-8'))
    for name,h in manifest['content_sha256'].items():assert sha(REPO/name)==h,('FrozenInputChanged',name)
    base=next(e for e in lines(RUN/'baseline.jsonl') if e['kind']=='snapshot')
    stats=Counter();branches={b:Counter() for b in manifest['fixture']['branches']}
    for row in summary['runs']:
        events=lines(RUN/f"{row['repetition']}-{row['branch']}.jsonl")
        assert [{k:v for k,v in e.items() if k!='kind'} for e in events if e['kind']=='branch_result']==[row]
        initial=next(e for e in events if e['kind']=='snapshot' and e['label']=='branch_initial')
        final=next(e for e in events if e['kind']=='snapshot' and e['label']=='branch_final')
        assert initial['snapshot_id']==base['snapshot_id']
        for snap in (initial,final):
            assert digest({k:v for k,v in snap.items() if k not in ('kind','label','snapshot_id')})==snap['snapshot_id']
        stats['identical_initial_snapshots']+=1
        records={key(r['ref']):r for r in final['records']}
        for old in initial['records']:assert records[key(old['ref'])]==old,('HistoricalRecordChanged',row)
        checks=[e for e in events if e['kind']=='check']
        assert all(c['passed']==(c['actual']==c['expected']) for c in checks)
        assert row['checks']==len(checks)
        assert row['failed_checks']==[{k:v for k,v in c.items() if k!='kind'} for c in checks if not c['passed']]
        stats['checks']+=len(checks);stats['failed_checks']+=sum(not c['passed'] for c in checks)
        calls=[e for e in events if e['kind']=='model_execution']
        assert row['model_calls']==len(calls)
        stats['model_calls']+=len(calls)
        stats.update('call_'+c['status'] for c in calls)
        policies=[e for e in events if e['kind']=='X_policy']
        by_digest={digest(e['candidate']):e for e in policies}
        for event in policies:
            candidate=event['candidate'];review=event['review'];context=event['context']
            assert candidate['protocol']==context['protocol']==review['protocol']
            assert candidate['context_id']==context['identity']==review['context_id']
            assert review['candidate_digest']==digest(candidate)
            assert context['versions']==candidate['record']['versions']
            generation=[c for c in calls if 'model-call:'+c['execution_id'] in candidate['record']['provenance']]
            assert len(generation)==1 and generation[0]['status']=='COMPLETED'
            assert json.loads(generation[0]['tool_calls'][0]['function']['arguments'])==payload(candidate['record'])
            model_items=json.loads(generation[0]['messages'][1]['content'])
            assert model_items==[{'ref':i['record']['ref'],'kind':i['record']['kind'],'content':payload(i['record'])} for i in context['items']]
            stats['exact_model_candidate_review_bindings']+=1
        commits=[e for e in events if e['kind']=='X_commit']
        for event in commits:
            c=by_digest[event['candidate_digest']]['candidate'];outcome=event['outcome']
            audit=records[key(outcome['audit_ref'])]
            assert audit['kind']=='CommitOutcome' and payload(audit)['candidate_digest']==digest(c)
            assert payload(audit)['status']==outcome['status']
            if outcome['status']=='Committed':
                standing=records[key(outcome['committed'])]
                assert standing['payload_json']==c['record']['payload_json']
                assert 'candidate-sha256:'+digest(c) in standing['provenance']
                stats['formal_policy_commits']+=1
            else:assert key(c['record']['ref']) not in records
        for r in records.values():
            if r['ref']['space']=='derived':
                assert any(a['kind']=='CommitOutcome' and payload(a).get('committed')==r['ref']
                           and payload(a)['status']=='Committed' for a in records.values())
        b=branches[row['branch']];b['attempted']+=1;b['complete']+=int(row['coverage']=='COMPLETE')
        b['passed']+=int(row['result']=='PASS')
        for e in (e for e in events if e['kind']=='X_effect'):
            intent=e['intent'];result=e['result']
            assert payload(result)['intent_ref']==intent['ref']
            p=records[key(payload(intent)['policy_ref'])]
            assert p['kind']=='PolicyOutcome'
            stats['effect_'+payload(result)['status']]+=1
        if row['coverage']!='COMPLETE':continue
        t1=next(r for r in initial['records'] if r['kind']=='TurnStarted')
        settle=next(r for r in final['records'] if r['kind']=='TurnSettled' and payload(r)['turn_ref']==t1['ref'])
        if row['branch']!='X2-revoke':
            t2=next(r for r in final['records'] if r['kind']=='TurnStarted' and r['ref']!=t1['ref'])
            assert settle['recorded_at']<t2['recorded_at']
            future=next(e for e in events if e['kind']=='X_future_context')['context']
            assert future['frozen_at']>=t2['recorded_at']
            stats['serial_two_turn_paths']+=1
        if row['branch']=='X1-correction':
            change=next(e for e in events if e['kind']=='X_owner_correction')
            assert change['outcome']['status']=='Committed'
            assert payload(change['correction'])['source']==change['source']['ref']
            assert change['correction']['corrects'] in [i['record']['ref'] for i in policies[0]['context']['items']]
            assert change['candidate']['record']['ref'] in [i['record']['ref'] for i in future['items']]
            assert row['commit_status']=='CandidateStale' and row['commit_reason']=='Corrected'
            assert not any(r['kind']=='ActionIntent' and payload(r)['policy_ref']==policies[0]['candidate']['record']['ref'] for r in records.values())
            stats['correction_stale_paths']+=1
        else:
            activate=next(e for e in events if e['kind']=='X_activation')['activation']
            assert activate['target']['revision']=='v2'
            assert policies[0]['context']['protocol']['revision']=='v1'
            assert policies[0]['context']['frozen_at']<activate['recorded_at']
            assert activate['recorded_at']<=records[key(commits[0]['outcome']['audit_ref'])]['recorded_at']
            assert row['commit_status']=='Committed'
            if row['branch']=='X2-supersede':
                assert row['effect_status']=='Occurred' and future['protocol']['revision']=='v2'
                assert activate['identity'] in future['versions']['activation_basis']
                stats['supersession_paths']+=1
            else:
                rev=next(e for e in events if e['kind']=='X_revocation')['record']
                effect=next(e for e in events if e['kind']=='X_effect')
                assert payload(rev)['target']==policies[0]['context']['protocol']
                assert key(payload(rev)['source']) in records
                assert effect['intent']['recorded_at']<rev['recorded_at']<=effect['result']['recorded_at']
                assert payload(effect['result'])['reason']=='EffectPrecondition:VersionIneligible'
                assert not any(r['kind'] in ('ActionOccurrence','DisplayAcknowledgement') for r in records.values())
                stats['revocation_paths']+=1
    assert stats['model_calls']==summary['model_calls']<=summary['max_model_calls']
    return {'schema':'composition-x1-x2-audit-v1','date':'2026-10-04','mechanical_audit':'PASS',
        'frozen_inputs_verified':len(manifest['content_sha256']),'baseline_snapshot':base['snapshot_id'],
        'counts':dict(stats),'branches':{k:dict(v) for k,v in branches.items()},
        'scope':'Mechanical exact-binding, no-mutation and temporal evidence audit; no E1 utility or production concurrency claim.',
        'evidence_sha256':{p.relative_to(REPO).as_posix():sha(p) for p in sorted(RUN.iterdir()) if p.is_file()}}


if __name__=='__main__':
    result=audit()
    (ROOT/'reports/composition-x1-x2-audit-20261004.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='evidence_sha256'},indent=2))
