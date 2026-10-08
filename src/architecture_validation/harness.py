"""Own-process HTTP/browser driver. Credentials stay in ignored run directories."""
from pathlib import Path
import json
import os
import socket
import subprocess
import sys
import time
from urllib.parse import urlencode
import httpx
from .common import ROOT, write_json


def wait_for(predicate,timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=predicate()
        if value:return value
        time.sleep(.05)
    raise TimeoutError('Validation condition not reached')


class Server:
    def __init__(self,path,model='scripted',phase='B2',policy='Hint',timeout=15,port=None,crash_point=None,budget_path=None):
        self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True)
        self.model=model;self.phase=phase;self.policy=policy;self.timeout=timeout;self.crash_point=crash_point
        self.budget_path=budget_path
        if port is None:
            with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        self.port=port;self.base=f'http://127.0.0.1:{port}';self.process=None;self.start()

    def start(self):
        env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'src')
        if self.crash_point:env['BUILD_TEST_CRASH_POINT']=self.crash_point
        else:env.pop('BUILD_TEST_CRASH_POINT',None)
        self.log=(self.path/'server.log').open('ab')
        args=[sys.executable,'-X','utf8','-m','architecture_validation.server','--db',str(self.path/'runtime.sqlite'),
              '--run-dir',str(self.path),'--port',str(self.port),'--model',self.model,'--phase',self.phase,'--policy',self.policy,'--effect-timeout',str(self.timeout)]
        if self.budget_path:args+=['--budget-path',str(self.budget_path)]
        self.process=subprocess.Popen(args,env=env,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=self.log,stderr=self.log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        def ready():
            if self.process.poll() is not None:raise RuntimeError('Server failed; inspect private server.log')
            try:return httpx.get(self.base+'/health',timeout=1,trust_env=False).status_code==200
            except httpx.HTTPError:return False
        try:wait_for(ready)
        except BaseException:self.stop();raise
        self.control=json.loads((self.path/'server.control.json').read_text(encoding='utf-8'))

    def request(self,path,body=None,admin=False,method=None):
        response=httpx.request(method or ('GET' if body is None else 'POST'),self.base+path,json=body,
            headers={'Authorization':'Bearer '+self.control['admin_token' if admin else 'learner_token']},timeout=15,trust_env=False)
        response.raise_for_status();return response.json()

    def task(self,ident='dev',quantity=6,total=42,target=15,noun='练习本'):
        return self.request('/admin/tasks',dict(id=ident,quantity=quantity,total=total,target=target,noun=noun),True)['id']

    def records(self,sid,kind=None):
        return self.request('/admin/records?'+urlencode({'sid':sid}|({'kind':kind} if kind else {})),admin=True)

    def submit(self,sid,text,task,key='1',correction=None):
        return self.request(f'/sessions/{sid}/inputs',{'key':key,'text':text,'task_id':task,'correction_of':correction})

    def state(self,sid):return self.request('/sessions/'+sid)

    def settled(self,sid,tid,timeout=240):
        return wait_for(lambda:next((t for t in self.state(sid)['turns'] if t['id']==tid and t['status'] in ('COMPLETED','FAILED','WAITING_EFFECT')),None),timeout)

    def page(self,browser,sid,task,settings=None):
        page=browser.new_page()
        if settings:page.add_init_script('window.addEventListener("DOMContentLoaded",()=>Object.assign(window.buildTest,'+json.dumps(settings)+'));')
        page.goto(self.base+'/#'+urlencode({'token':self.control['learner_token'],'session':sid,'task':task}))
        page.wait_for_function('window.channelEpoch && window.channelEpoch()>0')
        return page

    def stop(self,kill=False):
        if self.process and self.process.poll() is None:
            self.process.kill() if kill else self.process.terminate()
            self.process.wait(timeout=10)
        if hasattr(self,'log'):self.log.close()

    def restart(self):
        self.stop(True);self.crash_point=None;self.start()

    def __enter__(self):return self
    def __exit__(self,*args):self.stop()

    def export(self,name='records.json'):
        rows=self.request('/admin/records',admin=True)
        write_json(self.path/name,rows)
        return rows
