import json
import pytest
from architecture_validation.common import Rejected
from architecture_validation.model import Budget


def test_transient_windows_replace_failure_retries_local_write_only(tmp_path,monkeypatch):
    import architecture_validation.model as module
    actual=module.os.replace;calls=[]
    def busy_then_replace(src,dst):
        calls.append(1)
        if len(calls)==1:raise PermissionError('simulated sharing violation')
        actual(src,dst)
    monkeypatch.setattr(module.os,'replace',busy_then_replace)
    budget=Budget(tmp_path/'budget.json');ident=budget.reserve('B4','base',500,100,'test-logical')
    data=json.loads(budget.path.read_text(encoding='utf-8'))
    assert data['total_attempts']==1 and data['reservations'][ident]['status']=='RESERVED' and len(calls)==2


def test_persistent_local_failure_does_not_become_transport_retry(tmp_path,monkeypatch):
    import architecture_validation.model as module
    def busy(*args):raise PermissionError('simulated sharing violation')
    monkeypatch.setattr(module.os,'replace',busy);monkeypatch.setattr(module.time,'sleep',lambda _:None)
    budget=Budget(tmp_path/'budget.json')
    with pytest.raises(Rejected,match='LocalBudgetPersistenceFailure'):budget.reserve('B4','base',500,100,'test-logical')
    assert budget.data['total_attempts']==1 and budget.data['counts']['transport']==0
