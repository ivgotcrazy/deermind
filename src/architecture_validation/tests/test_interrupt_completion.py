import threading
import time
from architecture_validation.store import Store
from architecture_validation.runtime import Engine
from architecture_validation.testing import ScriptedModel
from architecture_validation.domain import task
from architecture_validation.harness import wait_for


def test_M08_A_running_worker_preserves_cancellation(tmp_path):
    st=Store(tmp_path/'cancel.sqlite');st.bootstrap();q=st.canonical(task('c',6,42,15));st.start_session('s')
    engine=Engine(st,ScriptedModel('Hint'),test_mode=True,effect_timeout=2)
    t=st.enqueue('s','1','input',q);st.claim_turn(engine.worker_epoch)
    worker=threading.Thread(target=engine.process,args=(t['id'],));worker.start()
    wait_for(lambda:st.rows('ActionIntent','s'));st.interrupt('s');worker.join(3)
    assert not worker.is_alive()
    assert st.turn(t['id'])['status']=='FAILED' and st.turn(t['id'])['error']=='UserInterrupted'
    assert not st.rows('ActionOccurrence','s') and len(st.rows('NotOccurred','s'))==1
