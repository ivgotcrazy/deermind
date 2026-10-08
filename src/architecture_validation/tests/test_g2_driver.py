import json

from architecture_validation.common import BASE
from architecture_validation.validate_g2 import probes,run_session,needs_inspection


def test_current_observation_probe_contract_keeps_originals():
    before=(BASE/'fixtures/probes-r1.json').read_bytes();items=probes()
    assert len(items)==12 and sum(p['expected']=='PASS' for p in items)==6
    assert all('current_purpose' not in p['candidate'] for p in items if p['purpose']=='Observation')
    assert (BASE/'fixtures/probes-r1.json').read_bytes()==before
    assert needs_inspection('InvalidStructuredOutput:ConflictingJSONKey:/x')
    assert not needs_inspection('RequiredValidationNotPassed')
    assert not needs_inspection('InjectedEvaluationFailure')


def test_campaign_driver_correction_and_injected_failure(tmp_path):
    cases=json.loads((BASE/'fixtures/holdout-r1.json').read_text(encoding='utf-8'))['sessions']
    for case in (cases[0],cases[4]):
        path=tmp_path/case['id'];dest=tmp_path/(case['id']+'.json')
        result=run_session(case,path,dest,model='scripted',budget_path=tmp_path/'unused-budget.json')
        assert result['status']=='MEASURED' and len(result['turns'])==4
        if case['id']=='S1':
            assert all(t['status']=='COMPLETED' for t in result['turns'])
            rows=json.loads((path/'records.json').read_text(encoding='utf-8'))
            assert any(r['kind']=='Observation' and r['revision']==2 for r in rows)
        else:
            assert result['turns'][1]['error']=='InjectedEvaluationFailure'
            assert result['turns'][2]['status']=='COMPLETED'
        assert not (tmp_path/'unused-budget.json').exists()
