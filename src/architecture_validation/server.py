"""Local controlled Build server; explicit learner/admin identities and single worker."""
import argparse
from contextlib import asynccontextmanager
import hmac
import os
from pathlib import Path
import secrets
import time
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict
import uvicorn

from .common import BASE, Rejected, write_json
from .domain import task
from .model import RealModel
from .runtime import Engine
from .store import Store
from .testing import ScriptedModel, FaultWrapper


class StrictBody(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
class NewSession(StrictBody):id:str
class Input(StrictBody):
    key:str;text:str;task_id:str;correction_of:str|None=None
class Epoch(StrictBody):epoch:int
class Ack(Epoch):dispatch_id:str;payload_hash:str;rendered:list[str]
class TaskInput(StrictBody):id:str;quantity:int;total:int;target:int;noun:str='练习本'
class Authority(StrictBody):allowed:bool
class Fault(StrictBody):purpose:str|None
class CanonicalInput(StrictBody):kind:str;id:str;version:str;body:dict
class RecomputeInput(StrictBody):observation_id:str;reason:str


def create_app(st,engine,learner_token,admin_token,shutdown=None,instance_id=None):
    @asynccontextmanager
    async def lifespan(app):
        engine.start()
        yield
        engine.stop()
    app=FastAPI(lifespan=lifespan)

    def role(request,required='learner'):
        token=request.headers.get('Authorization','').removeprefix('Bearer ')
        expected=admin_token if required=='admin' else learner_token
        if not hmac.compare_digest(token,expected):raise HTTPException(403,'Unauthorized')

    @app.exception_handler(Rejected)
    async def rejection(request,exc):return JSONResponse({'error':str(exc)},status_code=409)

    @app.get('/health')
    def health():return {'status':'ready','model_mode':engine.model.mode,'worker_epoch':engine.worker_epoch,'instance_id':instance_id}

    @app.get('/',response_class=HTMLResponse)
    def index():return (BASE/'static/index.html').read_text(encoding='utf-8')

    @app.post('/sessions')
    def new_session(body:NewSession,request:Request):role(request);return st.start_session(body.id)

    @app.get('/tasks/{task_id}')
    def task_statement(task_id:str,request:Request):
        role(request);record=st.get(task_id)
        if record['kind']!='TaskInstance':raise Rejected('InvalidTask')
        return {'id':task_id,'statement':record['body']['statement']}

    @app.get('/sessions/{sid}')
    def state(sid:str,request:Request):
        role(request)
        with st.lock:
            turns=[dict(r) for r in st.db.execute('SELECT * FROM turns WHERE sid=? ORDER BY created',(sid,))]
        return {'session':st.session(sid),'turns':turns}

    @app.get('/sessions/{sid}/history')
    def history(sid:str,request:Request):
        role(request);st.session(sid)
        items=[]
        for record in st.rows(sid=sid):
            if record['kind']=='Event' and record['body'].get('type')=='LearnerInput':
                items.append({'id':record['id'],'kind':'learner','text':record['body']['text']})
            elif record['kind']=='ActionOccurrence':
                for block in record['body']['blocks']:
                    items.append({'id':record['id']+':'+block['block_id'],'kind':'assistant','text':block['text']})
        return {'items':items}

    @app.post('/sessions/{sid}/inputs')
    def submit(sid:str,body:Input,request:Request):role(request);return st.enqueue(sid,body.key,body.text,body.task_id,correction_of=body.correction_of)

    @app.post('/sessions/{sid}/interrupt')
    def interrupt(sid:str,request:Request):role(request);st.interrupt(sid);return st.session(sid)

    @app.post('/channel/{sid}/dispatch')
    def dispatch(sid:str,body:Epoch,request:Request):role(request);return st.dispatch(sid,body.epoch)

    @app.post('/channel/{sid}/ack')
    def ack(sid:str,body:Ack,request:Request):role(request);return {'status':st.acknowledge(sid,body.dispatch_id,body.epoch,body.payload_hash,body.rendered)}

    @app.post('/channel/{sid}/stop')
    def stop(sid:str,body:Epoch,request:Request):role(request);return {'epoch':st.stop_channel(sid,body.epoch)}

    @app.post('/admin/tasks')
    def create_task(body:TaskInput,request:Request):role(request,'admin');return {'id':st.canonical(task(body.id,body.quantity,body.total,body.target,body.noun))}

    @app.post('/admin/canonical')
    def create_canonical(body:CanonicalInput,request:Request):role(request,'admin');return {'id':st.canonical(body.model_dump(),'admin')}

    @app.post('/admin/recompute')
    def recompute(body:RecomputeInput,request:Request):role(request,'admin');return st.request_recompute(body.observation_id,body.reason,'admin')

    @app.post('/admin/sessions/{sid}/authority')
    def authority(sid:str,body:Authority,request:Request):role(request,'admin');st.authorize(sid,body.allowed,'admin');return st.session(sid)

    @app.get('/admin/records')
    def records(request:Request,sid:str|None=None,kind:str|None=None):role(request,'admin');return st.rows(kind,sid)

    @app.post('/admin/shutdown')
    def stop_server(request:Request):
        role(request,'admin')
        if shutdown is None:raise Rejected('ShutdownUnavailable')
        with st.lock:
            sessions=[r[0] for r in st.db.execute('SELECT id FROM sessions WHERE active_turn IS NOT NULL').fetchall()]
        for sid in sessions:st.interrupt(sid)
        shutdown()
        return {'status':'STOPPING','preserves_database':True}

    @app.post('/admin/test/fault')
    def fault(body:Fault,request:Request):
        role(request,'admin')
        if body.purpose is not None and body.purpose not in ('Observation','Evidence','Belief','Policy'):raise Rejected('UnsupportedFault')
        engine.model.fail_next=body.purpose
        return {'configured':body.purpose,'scope':'declared synthetic validation fault'}

    return app


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--run-dir',required=True)
    p.add_argument('--port',type=int,default=8765);p.add_argument('--model',choices=['real','scripted'],required=True)
    p.add_argument('--phase',choices=['B2','B4'],default='B2');p.add_argument('--policy',default='Hint');p.add_argument('--effect-timeout',type=float,default=15)
    p.add_argument('--budget-path')
    p.add_argument('--instance-id')
    a=p.parse_args();lockfile=Path(a.db+'.worker.lock');lockfile.parent.mkdir(parents=True,exist_ok=True)
    guard=lockfile.open('a+b');guard.seek(0);guard.write(b'1');guard.flush();guard.seek(0)
    if os.name=='nt':
        import msvcrt
        msvcrt.locking(guard.fileno(),msvcrt.LK_NBLCK,1)
    else:
        import fcntl
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
    learner=secrets.token_urlsafe(24);admin=secrets.token_urlsafe(24)
    write_json(Path(a.run_dir)/'server.control.json',{'learner_token':learner,'admin_token':admin,'port':a.port})
    st=Store(a.db);st.bootstrap()
    model=RealModel(a.phase,Path(a.run_dir)/'model-calls',a.budget_path) if a.model=='real' else ScriptedModel(a.policy)
    hooks={}
    crash_point=os.environ.get('BUILD_TEST_CRASH_POINT') if a.model=='scripted' else None
    if crash_point:
        def crash(*args):
            marker=Path(a.run_dir)/'crash-marker.json';write_json(marker,{'point':crash_point,'pid':os.getpid()})
            os._exit(73)
        hooks[crash_point]=crash
    engine=Engine(st,FaultWrapper(model),test_mode=a.model=='scripted',effect_timeout=a.effect_timeout,hooks=hooks)
    def request_shutdown():server.should_exit=True
    app=create_app(st,engine,learner,admin,request_shutdown,a.instance_id)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=a.port,access_log=False,log_level='warning'))
    try:server.run()
    finally:engine.stop();guard.close()


if __name__=='__main__':main()
