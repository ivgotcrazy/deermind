"""Factual inventory of the bounded network follow-up; no model calls or labels."""
from collections import Counter, defaultdict
import json
from pathlib import Path

from foundation.single_task import ROOT
from foundation.candidate_spans import span
from foundation.runtime import ContractError
from run_network_retry import ABORTED, ORIGINAL, RUN, transport_failure, verify
from run_single_task_prototype import check_hashes, hashed, write

OUT = ROOT/'src/spike/reports/network-retry-analysis-20261007.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def category(turn):
    reason = turn.get('reason', '')
    if transport_failure(reason):
        return 'INCOMPLETE_TRANSPORT'
    if turn['execution'] not in ('COMPLETED', 'FAILED') or any(
            s in reason for s in ('BudgetExhausted', 'Deadline', 'UnexpectedRunnerFailure')):
        return 'INCOMPLETE_EXECUTION'
    if turn['execution'] == 'COMPLETED':
        return 'COMPLETED_PENDING_CONTENT_REVIEW'
    if reason == 'ContractError:workRejected:SemanticValidation:FAIL':
        return 'REVIEW_REJECTION'
    return 'CONTRACT_OR_OTHER_FAILURE'


def main():
    verify()
    for base in (RUN, ABORTED):
        check_hashes(read(base/'artifact-sha256.json'), base)
    check_hashes(read(RUN/'manifest.json')['source_sha256'], ROOT)
    result, records = read(RUN/'results.json'), read(RUN/'adapter-records.json')
    manifest, summary = read(RUN/'manifest.json'), read(RUN/'summary.json')
    targets = {(t['session'], t['turn']) for t in manifest['network_target_turns']}
    turns = [{'session':r['id'], 'turn':t['number'], 'execution':t['execution'],
              'reason':t.get('reason'), 'category':category(t),
              'original_transport_target':(r['id'],t['number']) in targets,
              'observation_committed':t.get('work_commit',{}).get('status')=='Committed',
              'policy_committed':t.get('policy_commit',{}).get('status')=='Committed',
              'phase':t.get('turn_phase'), 'outcome':t.get('outcome'),
              'displayed':t.get('displayed',[])} for r in result['rows'] for t in r['turns']]
    grouped=defaultdict(list)
    for record in records:
        grouped[record['logical_call']].append(record)
    retry_checks=[]
    for logical, attempts in grouped.items():
        if len(attempts)<2:
            continue
        original=attempts[0]
        unchanged=all(r['messages']==original['messages']
            and r.get('output_contract')==original.get('output_contract')
            and r['purpose']==original['purpose'] for r in attempts)
        eligible=all(transport_failure(r.get('failure')) for r in attempts[:-1])
        assert unchanged and eligible and len(attempts)<=3
        retry_checks.append({'logical_call':logical, **original['retry_context'],
            'purpose':original['purpose'], 'attempts':len(attempts),
            'prior_failures':[r.get('failure') for r in attempts[:-1]],
            'last_status':attempts[-1]['status'], 'identical_request':unchanged,
            'only_transport_retried':eligible})
    snapshots=[]
    recorded_ids=[]
    for file in sorted((RUN/'cases').glob('*.jsonl')):
        events=[json.loads(line) for line in file.read_text(encoding='utf-8').splitlines()]
        snapshots.append(next(e for e in reversed(events) if e['kind']=='snapshot'))
        recorded_ids += [e['execution_id'] for e in events if e['kind']=='model_execution']
    assert sorted(recorded_ids)==sorted(r['execution_id'] for r in records)
    old=read(ORIGINAL/'results.json')
    unaffected=[r['id'] for r in old['rows'] if not any(transport_failure(t.get('reason')) for t in r['turns'])]
    aborted_events=[json.loads(line) for file in (ABORTED/'cases').glob('*.jsonl')
                    for line in file.read_text(encoding='utf-8').splitlines()]
    aborted_turns=[{'turn':e['number'],'execution':e['execution'],'reason':e.get('reason')}
                    for e in aborted_events if e['kind']=='turn_result']
    abort=read(ABORTED/'summary.json')
    kinds=Counter(r['kind'] for snapshot in snapshots for r in snapshot['records'])
    diagnostics=[]
    for record in records:
        if not record.get('tool_calls'):
            continue
        body=json.loads(record['messages'][1]['content'])
        value=json.loads(record['tool_calls'][0]['function']['arguments'])
        finding={**record['retry_context'], 'execution_id':record['execution_id'],
                 'purpose':record['purpose']}
        if record['purpose']=='ObservationResponsibilityClassification':
            entries={x['handle']:x for x in body['candidate_registry']}
            finding['disallowed_role_selections']=[{**s,'text':''.join(entries[h]['text'] for h in s['span_ids'])}
                for s in value['segments'] if s['role'] not in ('local_observation','attributed_report')]
        if record['purpose']=='ObservationSemanticValidation':
            finding['arithmetic_status']=body['arithmetic_result']['status']
            finding['arithmetic_failures']=[{k:x.get(k) for k in ('text','speaker','stance','type','status')}
                for x in body['arithmetic_result']['checks'] if x['status'] in ('FAIL','UNRESOLVED')]
            finding['raw_criteria']=[{k:x[k] for k in ('id','status','rationale')} for x in value['criteria']]
        if isinstance(body,dict) and 'candidate_registry' in body:
            invalid=[]
            def inspect(item,path='$'):
                if isinstance(item,dict):
                    if 'span_ids' in item:
                        try:span(item['span_ids'],body['candidate_registry'])
                        except ContractError as exc:invalid.append({'path':path,'error':str(exc),'handles':item['span_ids']})
                    for key,child in item.items():inspect(child,path+'.'+key)
                elif isinstance(item,list):
                    for i,child in enumerate(item):inspect(child,path+'['+str(i)+']')
            inspect(value)
            finding['invalid_spans']=invalid
        if record.get('failure')=='OutputSchemaMismatch':
            finding['invalid_context_refs']=[r for r in value.get('context_refs',[])
                if r['space'] not in record['output_contract']['parameters']['properties']['context_refs']['items']['properties']['space']['enum']]
        diagnostics.append(finding)
    report={'status':'FACTUAL_ANALYSIS_COMPLETE', 'external_model_calls':0,
        'summary':summary, 'turns':turns,
        'category_counts':dict(Counter(t['category'] for t in turns)),
        'original_13_network_target_counts':dict(Counter(t['category'] for t in turns if t['original_transport_target'])),
        'failure_counts':dict(Counter(t['reason'] for t in turns if t['execution']=='FAILED')),
        'attempt_failure_counts':dict(Counter(r.get('failure') for r in records if r['status']=='FAILED')),
        'schema_valid_responses':sum(r['status']=='COMPLETED' for r in records),
        'maximum_input_chars':max(r['input_chars'] for r in records),
        'purpose_counts':dict(Counter(r['purpose'] for r in records)),
        'retried_requests':retry_checks, 'all_attempts_in_case_logs':True,
        'observation_commits':sum(t['observation_committed'] for t in turns),
        'policy_commits':sum(t['policy_committed'] for t in turns),
        'action_occurrences':kinds['ActionOccurrence'], 'evidence_records':kinds['Evidence'],
        'belief_records':kinds['LearnerBelief'],
        'original_sessions_without_transport_errors':unaffected,
        'original_nontransport_failures_remain_valid':True,
        'aborted_harness':{'summary':abort, 'preserved_turns':aborted_turns,
            'unrun_turns':18-len(aborted_turns),
            'cause':'Duplicate session keyword in EvidenceRecorder.emit; reproduced offline.',
            'old_script': 'src/spike/reports/source-baseline-network-retry-20261007/run_network_retry.py.txt'},
        'combined_actual_calls':abort['actual_model_calls']+len(records),
        'combined_execution_seconds':round(abort['elapsed_seconds']+summary['elapsed_seconds'],3),
        'no_network_failure_counted_as_semantic_failure':True,
        'fresh_outputs_do_not_isolate_network_causal_effect':True,
        'diagnostics':diagnostics,
        'semantic_quality_claimed':False,
        'source_sha256':{p.relative_to(ROOT).as_posix():hashed(p) for p in
                        (Path(__file__),RUN/'artifact-sha256.json',ABORTED/'artifact-sha256.json')}}
    assert report['combined_actual_calls']<=378
    assert report['combined_execution_seconds']<2701
    write(OUT,report)
    print(json.dumps({k:v for k,v in report.items() if k not in
        ('summary','turns','source_sha256','retried_requests','aborted_harness','diagnostics')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
