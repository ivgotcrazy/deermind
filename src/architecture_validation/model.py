"""Real DeepSeek JSON transport with a persistent, conservative stage budget."""
from pathlib import Path
import json
import math
import os
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from tokenizers import Tokenizer

from .common import BASE, ROOT, Rejected, dumps, now, strict_json, uid, write_json
from .model_output import parse_model_output,normalize_empty_extras


def load_config():
    values={}
    p=ROOT/'.env'
    if p.exists():
        for raw in p.read_text(encoding='utf-8-sig').splitlines():
            k,sep,v=raw.strip().partition('=')
            if sep and k.startswith('DEERMIND_LLM_'):values[k]=v.strip().strip('\"\'')
    values.update({k:v for k,v in os.environ.items() if k.startswith('DEERMIND_LLM_')})
    base=values.get('DEERMIND_LLM_BASE_URL','https://api.deepseek.com').rstrip('/')
    model=values.get('DEERMIND_LLM_MODEL','deepseek-flash');url=urlsplit(base)
    if url.scheme!='https' or url.hostname!='api.deepseek.com' or url.query or url.username:raise Rejected('UnpricedEndpoint')
    if model!='deepseek-flash':raise Rejected('UnpricedModel')
    key=values.get('DEERMIND_LLM_API_KEY','')
    if not key:raise Rejected('MissingAPIKey')
    return {'base_url':base,'model':model,'api_key':key}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class Budget:
    limits={'B2':40,'base':240,'repair':24,'probe':12,'transport':24}
    def __init__(self,path):
        self.path=Path(path);self.lock=threading.RLock()
        self.active_start=None;self.active_base=0
        self.data=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {
           'counts':{k:0 for k in self.limits},'total_attempts':0,'input_tokens':0,'output_tokens':0,'estimated_cny':0.0,'active_b4_seconds':0.0,'reservations':{}}
        self.policy=self.data.get('policy',{})
        self.limits=self.policy.get('category_limits',self.limits).copy()
        self.total_limit=self.policy.get('total_attempts',340)
        self.segment=None

    def start_active(self):
        self.active_base=self.data['active_b4_seconds'];self.active_start=time.monotonic()

    def refresh_active(self):
        if self.active_start is not None:self.data['active_b4_seconds']=self.active_base+time.monotonic()-self.active_start

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.pending')
        # Windows scanners/readers can briefly hold a target without delete sharing.
        # Retry only local persistence; this never repeats an HTTP request.
        for retry in range(6):
            try:
                with tmp.open('w',encoding='utf-8') as stream:
                    json.dump(self.data,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
                os.replace(tmp,self.path);return
            except PermissionError:
                if retry==5:raise Rejected('LocalBudgetPersistenceFailure')
                time.sleep(.05*(retry+1))

    def reserve(self,phase,category,input_bound,output_bound,logical_id):
        with self.lock:
            self.refresh_active()
            cat='B2' if phase=='B2' else category
            d=self.data;cost=(input_bound*2+output_bound*8)/1_000_000
            if d['total_attempts']>=self.total_limit or d['counts'][cat]>=self.limits[cat]:raise Rejected('CallBudgetExhausted')
            segments=d.setdefault('segment_counts',{})
            if phase=='B2' and self.policy and segments.get(self.segment,0)>=self.policy['development_segment_attempts']:raise Rejected('DevelopmentRoundBudgetExhausted')
            if d['input_tokens']+input_bound>self.policy.get('input_tokens',2_000_000) or d['output_tokens']+output_bound>self.policy.get('output_tokens',500_000) or d['estimated_cny']+cost>self.policy.get('cny',50):raise Rejected('ResourceBudgetExhausted')
            if (phase=='B4' or self.policy.get('active_all_phases')) and d['active_b4_seconds']>=self.policy.get('active_seconds',5400):raise Rejected('ExecutionTimeBudgetExhausted')
            attempt=uid('attempt');d['counts'][cat]+=1;d['total_attempts']+=1;d['input_tokens']+=input_bound;d['output_tokens']+=output_bound;d['estimated_cny']+=cost
            if self.segment:segments[self.segment]=segments.get(self.segment,0)+1
            d['reservations'][attempt]={'logical_id':logical_id,'input':input_bound,'output':output_bound,'cost':cost,'status':'RESERVED','segment':self.segment};self.save();return attempt

    def settle(self,attempt,usage,elapsed,phase,status):
        with self.lock:
            d=self.data;r=d['reservations'][attempt]
            if usage:
                ip=int(usage['prompt_tokens']);op=int(usage['completion_tokens']);cost=(ip*2+op*8)/1_000_000
                d['input_tokens']+=ip-r['input'];d['output_tokens']+=op-r['output'];d['estimated_cny']+=cost-r['cost']
                r.update(actual_input=ip,actual_output=op,actual_estimated_cny=cost)
            r['status']=status;r['seconds']=elapsed
            if phase=='B4' or self.policy.get('active_all_phases'):self.refresh_active()
            self.save()


class RealModel:
    mode='real'
    def __init__(self,phase,run_dir,budget_path=None):
        self.phase=phase;self.run_dir=Path(run_dir);self.run_dir.mkdir(parents=True,exist_ok=True)
        self.config=load_config();self.budget=Budget(budget_path or BASE/'reports/api-budget-v1.json')
        self.budget.segment=self.run_dir.parent.name
        self.consecutive_transport=0
        self.tokenizer=Tokenizer.from_file(str(BASE/'fixtures/deepseek-v4-tokenizer.json'))
        if phase=='B4' or self.budget.policy.get('active_all_phases'):self.budget.start_active()

    def public(self):
        return {k:v for k,v in self.config.items() if k!='api_key'}|{'thinking':'disabled','temperature':0,'response_format':'json_object','max_tokens':8192,'timeout':60}

    def complete(self,system,context,schema,purpose,category='base'):
        logical=uid('logical')
        messages=[{'role':'system','content':system+'\n输出 JSON schema：'+dumps(schema)}, {'role':'user','content':dumps(context)}]
        # Official offline tokenizer estimate with 25% margin and framing reserve.
        # API-reported usage is authoritative; no required material is truncated.
        estimate=sum(len(self.tokenizer.encode(m['content'],add_special_tokens=False).ids) for m in messages)
        bound=math.ceil(estimate*1.25)+512
        if bound>32000 or len(dumps(messages))>200000:raise Rejected('InputLimitExceeded')
        payload={'model':self.config['model'],'messages':messages,'response_format':{'type':'json_object'},'thinking':{'type':'disabled'},'temperature':0,'max_tokens':8192,'stream':False}
        for retry in range(3):
            if self.consecutive_transport>=3:raise Rejected('TransportPaused')
            if retry:time.sleep((1,3)[retry-1])
            attempt=self.budget.reserve(self.phase,category if not retry else 'transport',bound,8192,logical)
            record={'logical_id':logical,'attempt_id':attempt,'purpose':purpose,'category':category,'retry':retry,'started':now(),'config':self.public(),'messages':messages,'schema':schema,'input_admission_estimate':bound,'offline_tokens':estimate}
            started=time.perf_counter();usage=None;transport=False;failure=None
            try:
                req=urllib.request.Request(self.config['base_url']+'/chat/completions',data=dumps(payload).encode('utf-8'),
                     headers={'Authorization':'Bearer '+self.config['api_key'],'Content-Type':'application/json'},method='POST')
                with urllib.request.build_opener(NoRedirect()).open(req,timeout=60) as response:
                    raw=response.read(4_000_001)
                if len(raw)>4_000_000:raise Rejected('ProviderResponseTooLarge')
                result=strict_json(raw);usage=result.get('usage');choice=result['choices'][0]
                record.update(response_id=result.get('id'),response_model=result.get('model'),usage=usage,finish_reason=choice.get('finish_reason'),content=choice['message'].get('content'))
                if choice.get('finish_reason')!='stop':raise Rejected('IncompleteModelOutput')
                try:
                    output,normalization=parse_model_output(record['content'])
                except (ValueError,TypeError) as exc:
                    record['parse_error']=str(exc)
                    raise Rejected('InvalidStructuredOutput:'+str(exc)) from exc
                output,extra_repairs=normalize_empty_extras(output,schema)
                normalization['schema_adapter']='empty-extras-v1'
                normalization['repairs'].extend(extra_repairs)
                record['normalization']=normalization
                self.consecutive_transport=0;record['status']='COMPLETED'
            except urllib.error.HTTPError as e:
                transport=e.code==429 or 500<=e.code<600;failure='ProviderHTTP:'+str(e.code)
            except (urllib.error.URLError,OSError,TimeoutError):transport=True;failure='ProviderTransportFailure'
            except Rejected as e:failure=str(e)
            except (ValueError,KeyError,TypeError,IndexError):failure='InvalidStructuredOutput'
            elapsed=time.perf_counter()-started
            record.update(seconds=elapsed,completed=now())
            if failure:record.update(status='FAILED',failure=failure,transport_failure=transport)
            write_json(self.run_dir/(attempt+'.json'),record)
            self.budget.settle(attempt,usage,elapsed,self.phase,record['status'])
            if not failure:return output,record
            if transport:self.consecutive_transport+=1
            else:self.consecutive_transport=0
            if not transport or retry==2:raise Rejected(failure)
        raise Rejected('ProviderTransportFailure')
