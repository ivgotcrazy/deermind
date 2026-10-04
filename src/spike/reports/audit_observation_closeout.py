"""Offline audit of the reserved S1/S2 evidence; never calls a model or changes inputs."""
import json
import sys
from collections import Counter
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/spike'))
from foundation.structured_output import matches_schema
from foundation.responsibility import check_responsibility, combine_status
from foundation.arithmetic import check_arithmetic_extraction, combine_arithmetic_review
from foundation.source_handles import source_registry, expand_review
from foundation.claim_axes import checked_claim_axes
from foundation.source_conflicts import check_absence_review
from foundation.runtime import ContractError
from run_semantic_stability import summarize


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def audit():
    campaign = ROOT / 'src/spike/runs/observation-closeout-v1'
    manifest = read(campaign / 'manifest.json')
    hashes = manifest['content_sha256']
    assert all(sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    result = {'schema': 'observation-closeout-offline-audit-v1', 'date': '2026-10-04',
              'frozen_inputs_verified': len(hashes), 'new_model_calls': 0, 'batches': {}}
    for batch in ('S1', 'S2'):
        rows = [json.loads(line) for line in (campaign / batch / 'evidence.jsonl').read_text(encoding='utf-8').splitlines()]
        design = rows[0]
        fixture, protocol = design['fixture'], design['protocol']
        assert fixture == read(ROOT / f'src/spike/fixtures/observation-closeout-{batch.lower()}-v1.json')
        assert protocol == read(ROOT / 'src/spike/protocols/observation-smoke-v11.json')
        cases = [{k: v for k, v in r.items() if k != 'kind'} for r in rows if r['kind'] == 'case_result']
        executions = [r for r in rows if r['kind'] == 'model_execution']
        assert summarize(cases, fixture, len(executions)) == read(campaign / batch / 'summary.json')
        assert [{'case_id': r['case_id'], 'repetition': r['repetition']} for r in cases] == design['schedule']
        candidates = {(r['case_id'], r['repetition']): r for r in rows if r['kind'] == 'candidate'}
        by_call = {r['execution_id']: r for r in executions}
        raw, failures, fields, usage = {}, Counter(), Counter(), Counter()
        for r in executions:
            usage.update({k: v for k, v in r.get('usage', {}).items() if isinstance(v, int)})
            if r['status'] != 'COMPLETED':
                continue
            output = json.loads(r['tool_calls'][0]['function']['arguments'])
            assert matches_schema(output, r['output_contract']['parameters'])
            raw[r['execution_id']] = output
            request = json.loads(r['messages'][1]['content'])
            key = (r['case_id'], r['repetition'])
            candidate = candidates[key]['candidate']
            assert request['candidate'] == json.loads(candidate['record']['payload_json'])
            try:
                if r['purpose'] == 'ObservationResponsibilityClassification':
                    check_responsibility(output, request['candidate'])
                elif r['purpose'] == 'ArithmeticExtraction':
                    check_arithmetic_extraction(output, request['candidate'])
                else:
                    expanded = expand_review(output, source_registry(request['context']), protocol['inspection_encoding'])
                    check_absence_review(checked_claim_axes(expanded), request['candidate'], protocol['criteria'], request['context'], support_audit=True)
            except ContractError as exc:
                expected = next(c for c in cases if (c['case_id'], c['repetition']) == key)
                assert str(exc) == expected['reason']
                failures[str(exc)] += 1
                if str(exc) == 'InvalidResponsibilitySegment':
                    fields.update(s['field'] for s in output['segments'])
        checks, commits, snapshots = 0, 0, 0
        for r in rows:
            if r['kind'] == 'snapshot':
                body = {k: v for k, v in r.items() if k not in ('kind', 'label', 'snapshot_id')}
                assert digest(body) == r['snapshot_id']
                case_id, repetition, _ = r['label'].rsplit(':', 2)
                outcome = next(c for c in cases if c['case_id'] == case_id and c['repetition'] == int(repetition))
                if outcome.get('failure_type'):
                    assert not any(x['kind'] == 'Observation' for x in r['records'])
                snapshots += 1
            elif r['kind'] == 'validation_attempt':
                e, review = r['execution'], r['value']
                candidate = candidates[(r['case_id'], r['repetition'])]['candidate']
                assert e['candidate_digest'] == review['candidate_digest'] == digest(candidate)
                assert e['context_id'] == review['context_id'] == candidate['context_id']
                model = by_call[e['model_call']]
                request = json.loads(model['messages'][1]['content'])
                registry = source_registry(request['context'])
                assert registry == e['source_registry']
                assert raw[e['model_call']] == e['wire_output']
                expanded = expand_review(e['wire_output'], registry, protocol['inspection_encoding'])
                assert expanded == e['details'] == json.loads(review['details_json'])
                status, _, conflicts = check_absence_review(checked_claim_axes(expanded), request['candidate'], protocol['criteria'], request['context'], support_audit=True)
                assert status == e['semantic_status'] and conflicts == e['source_conflicts'] == []
                # Exact referenced intermediate executions live in the same immutable snapshot.
                snapshot = next(x for x in rows if x['kind'] == 'snapshot' and x['label'] == f"{r['case_id']}:{r['repetition']}:after")
                def intermediate(ref):
                    return json.loads(next(x['payload_json'] for x in snapshot['records'] if x['ref'] == ref))
                arithmetic = intermediate(e['arithmetic_execution'])
                responsibility = intermediate(e['responsibility_execution'])
                a = check_arithmetic_extraction(raw[arithmetic['model_call']], request['candidate'])
                c = check_responsibility(raw[responsibility['model_call']], request['candidate'])
                assert a == e['arithmetic_result'] and c == e['responsibility_result']
                status = combine_arithmetic_review(status, expanded, a)
                assert status == e['pre_responsibility_status']
                assert combine_status(status, c['status']) == e['status'] == review['status']
                checks += 1
            elif r['kind'] == 'commit':
                key = (r['case_id'], r['repetition'])
                candidate = candidates[key]['candidate']
                assert r['value']['candidate_digest'] == digest(candidate)
                snap = next(x for x in rows if x['kind'] == 'snapshot' and x['label'] == f'{key[0]}:{key[1]}:after')
                formal = [x for x in snap['records'] if x['ref'] == candidate['record']['ref']]
                if r['value']['status'] == 'Committed':
                    review = next(x['value'] for x in rows if x['kind'] == 'semantic_validation' and (x['case_id'], x['repetition']) == key)
                    expected = {**candidate['record'], 'provenance': candidate['record']['provenance'] + ['candidate-sha256:' + digest(candidate), review['identity']]}
                    assert formal == [expected] and r['value']['committed'] == expected['ref']
                    commits += 1
                else:
                    assert not formal and r['value']['committed'] is None
        result['batches'][batch] = {'schedule_and_summary_verified': True,
            'model_calls': len(executions), 'completed_wire_outputs_checked': len(raw),
            'validation_bindings_and_recomputed_outcomes': checks, 'formal_commits_verified': commits,
            'snapshots_verified': snapshots, 'reproduced_contract_failures': dict(failures),
            'invalid_responsibility_fields': dict(fields), 'reported_usage': dict(usage)}
    original = ROOT / 'src/spike/reports/assumption-aa-a02-v9-20261003.json'
    assert sha256(original.read_bytes()).hexdigest() == '369a5adb46358e9d3ca26d3f71be3a5b79ba761ec2dee0fd29a9e31e05daef1e'
    result['original_denial_unchanged'] = True
    result['status'] = 'PASS'
    return result


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
