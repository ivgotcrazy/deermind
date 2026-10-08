"""No semantic oracle: verify that one omitted/failed Claim cannot commit."""
import pytest
from architecture_validation.domain import task
from architecture_validation.runtime import Engine
from architecture_validation.store import Store
from architecture_validation.testing import ScriptedModel


@pytest.mark.parametrize('fault',['none','omitted','failed'])
def test_each_claim_is_reviewed_and_any_failure_blocks_evaluation(tmp_path,fault):
    store=Store(tmp_path/'runtime.sqlite');store.bootstrap();q=store.canonical(task('q',4,44,9));store.start_session('s')
    model=ScriptedModel();original=model.complete
    def call(system,context,schema,purpose,category='base'):
        output,record=original(system,context,schema,purpose,category)
        if purpose=='Review:Evidence':
            expected=[c['id']+':'+r for c in context['claims'] for r in ('claim','grounding','assistance','uncertainty')]
            assert [c['rule_id'] for c in output['checks']]==expected and len(expected)==12
            if fault=='omitted':output['checks'].pop()
            if fault=='failed':output['checks'][4]['verdict']='FAIL'  # Deliberately leave aggregate PASS.
        return output,record
    model.complete=call;engine=Engine(store,model,test_mode=True)
    turn=store.enqueue('s','1','mechanical fixture',q);store.claim_turn(engine.worker_epoch);engine.process(turn['id'])
    if fault=='none':
        assert store.turn(turn['id'])['status']=='COMPLETED'
        checks=[r['body']['checks'] for r in store.rows('Validation','s')]
        assert [len(c) for c in checks]==[4,12,12,4]
    else:
        assert store.turn(turn['id'])['status']=='FAILED'
        assert not store.rows('Evidence','s') and not store.rows('Belief','s') and not store.rows('Decision','s')
    store.db.close()
