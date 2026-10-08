"""Manual entry point: real processes and browser history, no paid model calls."""
import socket

import httpx
from playwright.sync_api import sync_playwright
import pytest

from architecture_validation.harness import wait_for
from architecture_validation.launcher import LaunchError, ManualService


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def test_manual_lifecycle_and_browser_history(tmp_path):
    service=ManualService('offline',tmp_path/'含空格 manual data')
    try:
        started=service.start(mode='scripted',port=free_port(),no_browser=True)
        assert started['running'] and not started['reused_process']
        state=service.state();sid=state['session_id']
        assert httpx.post(f"http://127.0.0.1:{state['port']}/admin/shutdown",json={},trust_env=False).status_code==403
        with sync_playwright() as pw:
            browser=pw.chromium.launch()
            page=browser.new_page();page.goto(started['url'])
            page.wait_for_function('window.channelEpoch && window.channelEpoch()>0')
            page.fill('#input','42÷6＝8，8×15＝120。请提示。');page.click('#send')
            page.wait_for_function("document.querySelectorAll('article[data-kind=assistant]').length===2")
            wait_for(lambda:service.request(state,f'/sessions/{sid}')['turns'][-1]['status']=='COMPLETED')
            history=service.request(state,f'/sessions/{sid}/history')['items']
            assert [h['kind'] for h in history]==['learner','assistant','assistant']
            before=service.request(state,f'/admin/records?sid={sid}&kind=ActionOccurrence',admin=True)
            page.reload();page.wait_for_function('window.channelEpoch && window.channelEpoch()>0')
            assert page.locator('article').all_text_contents()==[h['text'] for h in history]
            assert service.request(state,f'/admin/records?sid={sid}&kind=ActionOccurrence',admin=True)==before
            browser.close()
        reused=service.start(no_browser=True)
        assert reused['pid']==started['pid'] and reused['session_id']==sid and reused['reused_process']
        assert service.stop()['stopped'] and not service.status()['running']
        restarted=service.start(no_browser=True)
        assert restarted['session_id']==sid and not restarted['reused_process']
        assert service.request(service.state(),f'/sessions/{sid}/history')['items']==history
        another=service.start(new_session=True,no_browser=True,quantity=8,total=56,target=13,noun='绘画本')
        assert another['session_id']!=sid and another['pid']==restarted['pid']
        statement=service.request(service.state(),'/tasks/'+service.state()['task_id'])['statement']
        assert '8份绘画本共56元' in statement and '13份' in statement
        assert not (service.path/'manual-budget.json').exists()
    finally:
        service.stop()
    with pytest.raises(LaunchError,match='different -Name'):
        service.start(mode='real',no_browser=True)


def test_occupied_port_is_not_stopped(tmp_path):
    service=ManualService('occupied',tmp_path)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen()
        with pytest.raises(LaunchError,match='occupied'):
            service.start(mode='scripted',port=listener.getsockname()[1],no_browser=True)
        assert listener.getsockname()[1]>0 and service.state() is None


def test_manual_budget_keeps_usage_separate(tmp_path):
    from architecture_validation.model import Budget
    from architecture_validation.common import write_json
    service=ManualService('real',tmp_path)
    path=service.budget(40,3)
    data=Budget(path).data;data['total_attempts']=7;data['estimated_cny']=.25;write_json(path,data)
    service.budget()
    status=Budget(path).data
    assert status['total_attempts']==7 and status['estimated_cny']==.25
    assert status['policy']['total_attempts']==40 and status['policy']['active_all_phases'] is False
    with pytest.raises(LaunchError,match='below'):
        service.budget(max_calls=6)
