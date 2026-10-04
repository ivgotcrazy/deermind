"""Offline exact-standing, assistance lineage and denied replay audit."""
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1];RUN=ROOT/'runs/composition-x3-x4-v1'
def sha(p):return sha256(p.read_bytes()).hexdigest()
def digest(v):return sha256(json.dumps(v,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def lines(p):return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()]
def key(r):return tuple(r[k] for k in ('space','identity','revision'))
def payload(r):return json.loads(r['payload_json'])


def audit():
    manifest=json.loads((RUN/'manifest.json').read_text(encoding='utf-8'))
    summary=json.loads((RUN/'summary.json').read_text(encoding='utf-8'))
    for p,h in manifest['content_sha256'].items():assert sha(REPO/p)==h,('FrozenInputChanged',p)
    results={};case_events={}
    for row in summary['cases']:
        events=lines(RUN/(row['case_id']+'.jsonl'));case_events[row['case_id']]=events
        assert [{k:v for k,v in e.items() if k!='kind'} for e in events if e['kind']=='case_result']==[row]
        checks=[e for e in events if e['kind']=='check']
        assert len(checks)==row['checks'] and all(c['passed']==(c['actual']==c['expected']) for c in checks)
        assert not row['failed_checks'] and all(c['passed'] for c in checks)
        for snap in (e for e in events if e['kind']=='snapshot'):
            assert digest({k:v for k,v in snap.items() if k not in ('kind','label','snapshot_id')})==snap['snapshot_id']
            assert not any(r['kind'].startswith('LLM') for r in snap['records'])
            for r in snap['records']:
                if r['ref']['space']=='derived':
                    assert any(c['kind']=='CommitOutcome' and payload(c)['status']=='Committed'
                               and payload(c)['committed']==r['ref'] for c in snap['records'])
        results[row['case_id']]={'checks':len(checks),'execution_result':row['result']}
    x3=case_events['X3'];final=[e for e in x3 if e['kind']=='snapshot'][-1]
    records={key(r['ref']):r for r in final['records']}
    lineage=next(e for e in x3 if e['kind']=='X3_lineage')
    occurrence=records[key(lineage['occurrence'])];op=payload(occurrence)
    ack=records[key(op['acknowledgement_ref'])];intent=records[key(op['intent_ref'])]
    assert ack['kind']=='DisplayAcknowledgement' and payload(ack)['intent_ref']==intent['ref']
    assert op['actual_disclosure']=={'payload':payload(ack)['actual_payload'],'completeness':payload(ack)['completeness'],'rendered_at':payload(ack)['rendered_at']}
    response=records[key(lineage['response'])]
    old=[records[key(lineage[k])] for k in ('observation','evidence','belief')]
    correction=next(e['record'] for e in x3 if e['kind']=='X3_correction')
    assert occurrence['recorded_at']<response['recorded_at']<old[0]['recorded_at']<old[1]['recorded_at']<old[2]['recorded_at']<correction['recorded_at']
    assert correction['corrects']==old[0]['ref']
    row=next(r for r in summary['cases'] if r['case_id']=='X3')
    new=[records[key(r)] for r in row['new_chain']]
    assert correction['recorded_at']<new[0]['recorded_at']<new[1]['recorded_at']<new[2]['recorded_at']
    assert occurrence['ref'] in [d['target'] for d in new[1]['dependencies']]
    assert new[0]['ref'] in [d['target'] for d in new[1]['dependencies']]
    assert new[1]['ref'] in [d['target'] for d in new[2]['dependencies']]
    stale=next(e['outcome'] for e in x3 if e['kind']=='X3_stale_commit')
    assert stale['status']=='CandidateStale' and stale['reason']=='Corrected'
    assert all('candidate-sha256:'+stale['candidate_digest'] not in r['provenance'] for r in records.values())
    assert sum(r['kind']=='ActionOccurrence' for r in records.values())==1
    assert all(e['result']['current'] is None and e['result']['reason']=='Corrected' for e in x3 if e['kind']=='X3_old_exact_resolution')
    exposures=[e['value'] for e in x3 if e['kind']=='exposure_view']
    assert exposures[0]==exposures[-1] and exposures[0]['exposures'][0]['before_response']
    results['X3'].update(formal_derived_records=sum(r['ref']['space']=='derived' for r in records.values()),
        immutable_occurrences=1,stale_candidate_rejections=1,restored_revisions=3)
    x4=case_events['X4'];snaps=[e for e in x4 if e['kind']=='snapshot']
    base=next(s for s in snaps if s['label']=='X4 shared baseline')
    initials=[s for s in snaps if s['label'].startswith('X4 initial')]
    assert len(initials)==3 and all(s['snapshot_id']==base['snapshot_id'] for s in initials)
    operations=[e for e in x4 if e['kind']=='X4_operation']
    denied=[e for e in operations if e['result']['capability']=='UNAVAILABLE']
    allowed=[e for e in operations if e['result']['capability']=='FULL']
    assert len(denied)==6 and len(allowed)==8
    for e in denied:
        r=e['result'];assert r['reasons']==['DataAuthorityDenied']
        assert r['historical_view'] is None and r['generated_output'] is None
        assert not e['artifact_loads'] and not e['provider_inputs']
        if not e['label'].startswith('raw-data-denied'):assert not e['payload_reads']
    signals=0
    for snap in (s for s in snaps if s['label'].startswith('X4 final')):
        rs={key(r['ref']):r for r in snap['records']}
        for original in base['records']:assert rs[key(original['ref'])]==original
        for r in rs.values():
            if r['kind']=='SecuritySignal':
                p=payload(r);source=rs[key(p['source'])]
                assert source['kind']=='ReplayRequested'
                assert p['reason']=='NoMatchingDataUseGrant' and p['decision']=='DENY'
                assert p['data_use']['purpose']==p['request']['purpose']
                signals+=1
    assert signals==6
    results['X4'].update(shared_initial_snapshots=3,denied_operations=6,allowed_operations=8,
        source_linked_security_signals=signals,fixture_provider_invocations=sum(len(e['provider_inputs']) for e in operations))
    assert results['X4']['fixture_provider_invocations']==4
    return {'schema':'composition-x3-x4-audit-v1','date':'2026-10-04','mechanical_audit':'PASS',
        'frozen_inputs_verified':len(manifest['content_sha256']),'cases':results,'external_model_calls':0,
        'evidence_sha256':{p.relative_to(REPO).as_posix():sha(p) for p in sorted(RUN.iterdir()) if p.is_file()}}


if __name__=='__main__':
    result=audit();(ROOT/'reports/composition-x3-x4-audit-20261004.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
