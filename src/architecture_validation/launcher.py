"""Local manual-test lifecycle. No learner submission or model call on startup."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from urllib.parse import urlencode
import webbrowser

import httpx

from .common import BASE, ROOT, Rejected, now, uid, write_json
from .model import Budget, load_config


class LaunchError(Exception):
    pass


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


@contextmanager
def control_lock(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    stream=path.open('a+b');stream.seek(0);stream.write(b'1');stream.flush();stream.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError as exc:
        stream.close()
        raise LaunchError('Another launch command is running for this Name; retry shortly.') from exc
    try:
        yield
    finally:
        stream.close()


class ManualService:
    def __init__(self,name='default',root=None):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,47}',name):
            raise LaunchError('Name must contain only letters, digits, underscores or hyphens.')
        self.name=name;self.root=Path(root or BASE/'runs/manual').resolve()
        self.path=(self.root/name).resolve()
        if self.path.parent!=self.root:raise LaunchError('Invalid manual run directory.')
        self.state_path=self.path/'launcher.json'

    def state(self):
        return read(self.state_path) if self.state_path.exists() else None

    def health(self,state):
        try:
            response=httpx.get(f"http://127.0.0.1:{state['port']}/health",timeout=1,trust_env=False)
            response.raise_for_status();value=response.json()
            return value if value.get('instance_id')==state['instance_id'] else None
        except (httpx.HTTPError,ValueError):return None

    def request(self,state,path,body=None,admin=False):
        control=read(self.path/'server.control.json')
        token=control['admin_token' if admin else 'learner_token']
        try:
            response=httpx.request('GET' if body is None else 'POST',f"http://127.0.0.1:{state['port']}"+path,
                json=body,headers={'Authorization':'Bearer '+token},timeout=5,trust_env=False)
            if response.status_code>=400:
                raise LaunchError('Service request failed: '+str(response.status_code)+' '+response.text[:160])
            return response.json()
        except httpx.HTTPError as exc:raise LaunchError('Local service did not respond.') from exc

    def budget(self,max_calls=None,max_cost=None):
        path=self.path/'manual-budget.json';budget=Budget(path)
        limits=budget.data.get('policy',{})
        calls=max_calls if max_calls is not None else limits.get('total_attempts',200)
        cost=max_cost if max_cost is not None else limits.get('cny',10)
        if calls<budget.data['total_attempts'] or cost<budget.data['estimated_cny']:
            raise LaunchError('Requested budget is below already recorded usage; history will not be reset.')
        budget.data['policy']={'category_limits':{'B2':calls,'base':0,'repair':0,'probe':0,'transport':0},
            'total_attempts':calls,'development_segment_attempts':calls,'input_tokens':calls*32000,
            'output_tokens':calls*8192,'cny':cost,'active_all_phases':False}
        budget.data['campaign']='MANUAL:'+self.name
        budget.save()
        return path

    def start(self,*,mode=None,port=None,new_session=False,no_browser=False,
              quantity=None,total=None,target=None,noun=None,max_calls=None,max_cost=None):
        self.path.mkdir(parents=True,exist_ok=True)
        with control_lock(self.path/'launcher.lock'):
            prior=self.state();running=bool(prior and self.health(prior))
            mode=mode or (prior['mode'] if prior else 'real')
            port=port if port is not None else (prior['port'] if prior else 8765)
            if prior and prior['mode']!=mode:
                raise LaunchError('Use a different -Name when switching real/scripted mode; their histories must stay separate.')
            if running and (prior['mode']!=mode or prior['port']!=port):
                raise LaunchError('This Name is running with different settings. Stop it first or use another -Name.')
            if running and (max_calls is not None or max_cost is not None):
                raise LaunchError('Stop this service before changing its budget; existing usage will be preserved.')
            state=prior if running else None
            if not running:
                if mode=='real':
                    try:load_config()
                    except Rejected as exc:
                        if str(exc)=='MissingAPIKey':raise LaunchError('Set DEERMIND_LLM_API_KEY in the repository .env, or use -Mode scripted.') from exc
                        raise LaunchError(str(exc)) from exc
                with socket.socket() as check:
                    try:check.bind(('127.0.0.1',port))
                    except OSError as exc:raise LaunchError(f'Port {port} is occupied. Use -Port with a free port; no other process was stopped.') from exc
                budget=self.budget(max_calls,max_cost) if mode=='real' else None
                instance=uid('manual');env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'src')
                env.pop('BUILD_TEST_CRASH_POINT',None)
                args=[sys.executable,'-X','utf8','-m','architecture_validation.server','--db',str(self.path/'runtime.sqlite'),
                      '--run-dir',str(self.path),'--model',mode,'--phase','B2','--port',str(port),'--instance-id',instance]
                if budget:args+=['--budget-path',str(budget)]
                with (self.path/'server.log').open('ab') as log:
                    flags=(subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0
                    process=subprocess.Popen(args,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                        creationflags=flags,start_new_session=os.name!='nt')
                state={'instance_id':instance,'pid':process.pid,'port':port,'mode':mode,'created':now(),
                       'session_id':prior.get('session_id') if prior else None,'task_id':prior.get('task_id') if prior else None,
                       'task_parameters':prior.get('task_parameters') if prior else None}
                write_json(self.state_path,state)
                deadline=time.monotonic()+30
                while not self.health(state):
                    if process.poll() is not None:raise LaunchError('Service startup failed. Inspect '+str(self.path/'server.log'))
                    if time.monotonic()>deadline:
                        process.terminate();process.wait(timeout=5)
                        raise LaunchError('Service startup timed out. Inspect '+str(self.path/'server.log'))
                    time.sleep(.1)
            changed_task=any(v is not None for v in (quantity,total,target,noun))
            if new_session or changed_task or not state.get('session_id'):
                params=state.get('task_parameters') or {'quantity':6,'total':42,'target':15,'noun':'练习本'}
                params=params|{k:v for k,v in {'quantity':quantity,'total':total,'target':target,'noun':noun}.items() if v is not None}
                task_id=self.request(state,'/admin/tasks',{'id':uid('manual-task'),**params},True)['id']
                sid=uid('manual-session');self.request(state,'/sessions',{'id':sid})
                state.update(session_id=sid,task_id=task_id,task_parameters=params)
                write_json(self.state_path,state)
            control=read(self.path/'server.control.json')
            url=f'http://127.0.0.1:{port}/#'+urlencode({'session':state['session_id'],'task':state['task_id'],'token':control['learner_token']})
            state['url']=url;write_json(self.state_path,state)
            if not no_browser:webbrowser.open(url,new=2)
            return self.status()|{'url':url,'reused_process':running}

    def status(self):
        state=self.state()
        if not state:return {'running':False,'name':self.name,'data_directory':str(self.path)}
        result={'running':bool(self.health(state)),'name':self.name,'mode':state['mode'],'port':state['port'],
                'pid':state['pid'],'session_id':state.get('session_id'),'data_directory':str(self.path),
                'log':str(self.path/'server.log')}
        path=self.path/'manual-budget.json'
        if path.exists():
            budget=read(path);result['budget']={'calls_used':budget['total_attempts'],'calls_limit':budget['policy']['total_attempts'],
                'estimated_cny_used':round(budget['estimated_cny'],4),'cny_limit':budget['policy']['cny']}
        return result

    def stop(self):
        with control_lock(self.path/'launcher.lock'):
            state=self.state()
            if not state or not self.health(state):return {'running':False,'name':self.name,'stopped':False}
            self.request(state,'/admin/shutdown',{},True)
            deadline=time.monotonic()+12
            while self.health(state):
                if time.monotonic()>deadline:raise LaunchError('Shutdown is still pending. Check status and server.log; no unrelated process was terminated.')
                time.sleep(.1)
            return {'running':False,'name':self.name,'stopped':True,'data_directory':str(self.path)}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['start','stop','status'])
    p.add_argument('--name',default='default');p.add_argument('--mode',choices=['real','scripted']);p.add_argument('--port',type=int)
    p.add_argument('--new-session',action='store_true');p.add_argument('--no-browser',action='store_true')
    for field in ('quantity','total','target'):p.add_argument('--'+field,type=int)
    p.add_argument('--noun');p.add_argument('--max-calls',type=int);p.add_argument('--max-cost',type=float)
    a=p.parse_args()
    for field in ('quantity','total','target','max_calls','max_cost'):
        if getattr(a,field) is not None and getattr(a,field)<=0:p.error(field+' must be positive')
    if a.port is not None and not 1024<=a.port<=65535:p.error('port must be 1024..65535')
    try:
        service=ManualService(a.name)
        if a.action=='start':result=service.start(**{k:v for k,v in vars(a).items() if k not in ('action','name')})
        else:result=getattr(service,a.action)()
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (LaunchError,Rejected) as exc:
        print('DeerMind: '+str(exc),file=sys.stderr);return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
