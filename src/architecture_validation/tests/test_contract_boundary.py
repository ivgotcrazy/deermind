import pytest

from architecture_validation.common import Rejected
from architecture_validation.contracts import WIRE,validate
from architecture_validation.domain import task
from architecture_validation.references import Bindings
from architecture_validation.runtime import Engine,view
from architecture_validation.store import Store
from architecture_validation.testing import ScriptedModel


def test_activity_is_bound_by_backend_and_action_enum_tracks_transition(tmp_path):
    st=Store(tmp_path/'runtime.sqlite');st.bootstrap();q=st.canonical(task('q',6,42,15));st.start_session('s')
    engine=Engine(st,ScriptedModel(),test_mode=True)
    turn=st.enqueue('s','1','请完整讲解。',q);st.claim_turn(engine.worker_epoch)
    obs=engine.step(turn['id'],'Observation')[0][0]
    candidate=st.rows('Candidate','s')[0]['body']
    assert 'current_purpose' not in candidate['wire']
    assert st.get(obs)['body']['current_purpose']=='IndependentDiagnosis'
    ctx=engine.context(turn['id'],'Observation');bindings=Bindings(st,st.get(ctx))
    injected=candidate['wire']|{'current_purpose':'Teaching'}
    with pytest.raises(Rejected,match='SchemaMismatch'):
        validate(bindings.schema('Observation',WIRE['Observation']),injected)
    with pytest.raises(Rejected,match='RuntimeOwnedField'):
        engine.materialize(turn['id'],'Observation',injected,ctx)
    # Same observation survives the activity transition; its historical label is
    # not presented as the policy's current state. No semantic decision is forced.
    ev=engine.step(turn['id'],'Evidence',obs)[0]
    beliefs,unchanged,ctx=engine.step(turn['id'],'Belief',obs)
    completion=engine.evaluation_completion(turn['id'],ev,beliefs,unchanged,ctx,obs)
    for activity,expected in [('IndependentDiagnosis',['Hint','Control','None']),('Teaching',['Hint','Explanation','None'])]:
        with st.lock:st.db.execute('UPDATE sessions SET purpose=? WHERE id=?',(activity,'s'))
        ctx=engine.context(turn['id'],'Policy',obs,completion);bindings=Bindings(st,st.get(ctx))
        schema=bindings.schema('Policy',WIRE['Policy'])
        assert schema['properties']['action_type']['enum']==expected
        projected=bindings.project(view(st.get(obs)))
        assert projected['body']['activity_at_observation']=='IndependentDiagnosis'
        assert 'current_purpose' not in projected['body']
        proposal,_=ScriptedModel('Control').complete('',bindings.project(st.get(ctx)['body']['semantic']),schema,'Policy')
        validate(schema,proposal)
        if activity=='Teaching':
            proposal['action_type']='Control'
            with pytest.raises(Rejected,match='SchemaMismatch:action_type'):validate(schema,proposal)
