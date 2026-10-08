from copy import deepcopy
import pytest
from architecture_validation import contracts as c
from architecture_validation.common import Rejected, digest
from architecture_validation.domain import definitions, exact, task


def test_normative_coordinates_and_claim_support_are_distinct():
    rows=definitions(); byid={r['id']:r for r in rows}
    for r in rows:c.validate(c.NORM[r['kind']],r['body'])
    assert byid['claim-task']['body']['responsibility_boundary']['allowed_support']==[]
    assert byid['claim-division']['body']['responsibility_boundary']['allowed_support']
    assert all(r['kind'] not in ('Belief','Evidence') for r in rows)
    c.validate(c.TASK,task('dev',6,42,15)['body'])


def test_structural_positive_and_negative_examples():
    claim=next(r['body'] for r in definitions() if r['id']=='claim-task')
    invalid=deepcopy(claim);invalid['mastered']=True
    with pytest.raises(Rejected):c.validate(c.CLAIM,invalid)
    ref=exact('Claim','claim-task',claim)
    c.check_ref(ref)
    with pytest.raises(Rejected):c.check_ref({**ref,'revision':1})
    with pytest.raises(Rejected):c.validate(c.REVIEW,{'verdict':'PASS','checks':[],'authority':'admin'})


def test_unknown_is_not_execution_failure():
    b={'items':[{'claim_id':'claim-task','disposition':'REVISE','assessment_kind':'UNKNOWN','assessment':'尚无足够依据',
        'uncertainty':'缺少作答','epistemic_status':['EvidenceSparse'],'evidence_ids':[],'conflicts':[],'rationale':'只有请求'}]}
    c.validate(c.WIRE['Belief'],b)
    failed=deepcopy(b);failed['items'][0]['assessment_kind']='FAILED'
    with pytest.raises(Rejected):c.validate(c.WIRE['Belief'],failed)
    ref=exact('Context','c',{})
    completion={'turn_id':'t','input_context_ref':ref,'execution_refs':[],'validation_refs':[],
                'execution_status':'FAILED','evidence_refs':[],'belief_results':[],'failure_reason':'ProviderTimeout'}
    c.validate(c.COMPLETION,completion)
