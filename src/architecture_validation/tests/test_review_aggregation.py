import json
import pytest
from architecture_validation.common import BASE
from architecture_validation.review import aggregate_review
from architecture_validation.domain import task
from architecture_validation.runtime import Engine
from architecture_validation.store import Store
from architecture_validation.testing import ScriptedModel


def test_original_inconsistent_reviews_keep_every_check_unchanged():
    cases=json.loads((BASE/'fixtures/review-aggregation-regression-r3.json').read_text(encoding='utf-8'))['cases']
    assert len(cases)==6
    for case in cases:
        before=json.dumps(case['review'],ensure_ascii=False)
        assert case['review']['verdict']=='FAIL' and aggregate_review(case['review'])=='PASS'
        assert json.dumps(case['review'],ensure_ascii=False)==before


@pytest.mark.parametrize('child,expected',[('PASS','COMPLETED'),('FAIL','FAILED'),('UNRESOLVED','FAILED'),('MISSING','FAILED')])
def test_owner_commit_uses_complete_checks_and_audits_raw_verdict(tmp_path,child,expected):
    st=Store(tmp_path/'runtime.sqlite');st.bootstrap();q=st.canonical(task('q',6,42,15));st.start_session('s')
    model=ScriptedModel();original=model.complete
    def complete(system,context,schema,purpose,category='base'):
        output,record=original(system,context,schema,purpose,category)
        if purpose=='Review:Evidence':
            output['verdict']='FAIL' if child=='PASS' else 'PASS'
            if child=='MISSING':output['checks'].pop()
            else:output['checks'][0]['verdict']=child
        return output,record
    model.complete=complete;engine=Engine(st,model,test_mode=True)
    turn=st.enqueue('s','1','mechanism fixture',q);st.claim_turn(engine.worker_epoch);engine.process(turn['id'])
    assert st.turn(turn['id'])['status']==expected
    if child=='PASS':
        validations=[r for r in st.rows('Validation','s') if r['body'].get('model_verdict')=='FAIL']
        assert len(validations)==1 and validations[0]['body']['verdict']=='PASS'
        assert len(st.rows('Evidence','s'))==3 and len(st.rows('Belief','s'))==3
    else:assert not st.rows('Evidence','s') and not st.rows('Decision','s')
    st.db.close()


def test_absent_or_unsupported_check_verdict_is_not_success():
    for checks in ([],[{'reason':'x'}],[{'verdict':'PASS','reason':''}],[{'verdict':'unknown','reason':'x'}]):
        assert aggregate_review({'verdict':'PASS','checks':checks})=='UNRESOLVED'
