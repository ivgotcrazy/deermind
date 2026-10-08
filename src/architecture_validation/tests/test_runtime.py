from pathlib import Path
import pytest
from architecture_validation.store import Store
from architecture_validation.runtime import Engine
from architecture_validation.testing import ScriptedModel
from architecture_validation.domain import task
from architecture_validation.harness import Server,wait_for
from playwright.sync_api import sync_playwright


def test_persistent_normal_and_evaluation_failure(tmp_path):
    st=Store(tmp_path/'unit.sqlite');st.bootstrap();q=st.canonical(task('dev',6,42,15,'练习本'));st.start_session('s')
    model=ScriptedModel();engine=Engine(st,model,test_mode=True)
    for index in range(2):
        if index:model.fail_next='Evidence'
        t=st.enqueue('s',str(index),'原始计算',q);st.claim_turn(engine.worker_epoch);engine.process(t['id'])
        assert st.turn(t['id'])['status']==('FAILED' if index else 'COMPLETED')
    assert len(st.rows('Decision','s'))==1
    assert [r['body']['execution_status'] for r in st.rows('EvaluationCompletion','s')]==['SUCCEEDED','FAILED']


def test_browser_actual_occurrence(tmp_path):
    with Server(tmp_path/'browser') as srv,sync_playwright() as pw:
        browser=pw.chromium.launch();q=srv.task();page=srv.page(browser,'s',q)
        assert '42' in page.locator('#task').inner_text()
        page.fill('#input','请给一点提示');page.click('#send')
        t=wait_for(lambda:next(iter(srv.state('s')['turns']),None));result=srv.settled('s',t['id'])
        assert result['status']=='COMPLETED',result
        assert page.locator('article[data-kind=assistant]').count()==2
        assert page.locator('article[data-kind=learner]').count()==1
        assert srv.records('s','ActionOccurrence')[0]['body']['completeness']=='FULL'
        page.close();browser.close()
