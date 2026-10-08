from types import SimpleNamespace
from architecture_validation.store import Store
from architecture_validation.runtime import Engine
from architecture_validation.testing import ScriptedModel
from architecture_validation.domain import task


def test_exhausted_repair_reserve_keeps_remaining_base_work_eligible(tmp_path):
    st=Store(tmp_path/'budget.sqlite');st.bootstrap();q=st.canonical(task('b',6,42,15));st.start_session('s')
    m=ScriptedModel();m.phase='B4';m.budget=SimpleNamespace(data={'counts':{'repair':24},'total_attempts':168},limits={'repair':24})
    m.review_verdict='FAIL';e=Engine(st,m,test_mode=True)
    t=st.enqueue('s','1','input',q);st.claim_turn(e.worker_epoch);e.process(t['id'])
    assert st.turn(t['id'])['error']=='RequiredValidationNotPassed' and len(m.calls)==2
    assert st.rows('RecoveryOmitted','s')
    m.review_verdict='PASS'
    t=st.enqueue('s','2','next planned input',q);st.claim_turn(e.worker_epoch);e.process(t['id'])
    assert st.turn(t['id'])['status']=='COMPLETED'
