"""One six-call v3 identification campaign; prepare first, real run requires --run."""
import argparse,copy,json
from dataclasses import replace
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from foundation.boundary import digest
from foundation.cases import EvidenceRecorder
from foundation.llm import DeepSeekAdapter,LLMConfig,load_config,ModelFailure
from foundation.policy_cases import PolicyWorld
from foundation.policy_disposition import RULES
from foundation.runtime import ContractError
from foundation.records import json_value
from run_policy_validation import load_design
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
PACK=ROOT/'review-packages/policy-disposition-real-v1'
RUN=ROOT/'runs/policy-disposition-real-v1'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def setup(e,spec,definition,fixture,sources):
    variant=next(x for x in fixture['variants'] if x['id']==spec['variant'])
    w=PolicyWorld(e,definition,fixture,variant,rule_revision='v3')
    payload=copy.deepcopy(sources[spec['source_id']]['candidate'])
    # Preserve complete free-text and action payloads; bind citations to this exact registered formation context.
    payload['context_refs']=[json_value(i.record.ref) for i in w.context.items]
    candidate=w.runtime.propose(w.context,'P','r1',payload)
    if spec['withhold']:w.runtime.withhold_policy_review_material(w.context,tuple(getattr(w,name) for name in spec['withhold']))
    e.emit('fixed_candidate',candidate=json_value(candidate),source_id=spec['source_id'],author_expected=spec['author_expected'])
    return w,candidate

def sample(body):
    source=next(x for x in body['context'] if x['kind']=='CurrentInteractionInput');text=source['content']['text'];ct=body['candidate']['rationale']
    f={'id':'f1','rules':list(RULES),'relation':'SUPPORTED','candidate_quotes':[{'field':'rationale','start':'0','end':str(len(ct)),'quote':ct}],
        'source_quotes':[{'ref':source['ref'],'field':'text','start':'0','end':str(len(text)),'quote':text}],'gap_ids':[],'rationale':'Offline declared fixture only.'}
    return {k:body[k] for k in ('candidate_digest','context_id','rule_ref','material_record_ref')}|{'reviewed_fields':list(body['candidate']),
        'checks':[{'id':r,'status':'PASS','reason_code':'SATISFIED','finding_ids':['f1'],'rationale':'Offline.'} for r in RULES],
        'findings':[f],'review_material_gaps':[],'status':'PASS','rationale':'Offline.'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');args=parser.parse_args()
    plan=read(ROOT/'fixtures/policy-disposition-real-v1.json');definition=read(ROOT/'protocols/policy-e1-v3.json');fixture,_=load_design()
    sourcepath=ROOT/'review-packages/policy-e1-v2-reviewed/cases.json';sources={x['id']:x for x in read(sourcepath)}
    inputs=[Path(__file__),ROOT/'fixtures/policy-disposition-real-v1.json',ROOT/'protocols/policy-e1-v3.json',sourcepath,
        ROOT/'foundation/boundary.py',ROOT/'foundation/policy_cases.py',ROOT/'foundation/policy_disposition.py',ROOT/'foundation/llm.py']
    hashes={p.relative_to(REPO).as_posix():sha(p) for p in inputs}
    if not args.run:
        PACK.mkdir(parents=True,exist_ok=False);sizes=[]
        for spec in plan['cases']:
            e=EvidenceRecorder(PACK/(spec['id']+'.jsonl'))
            try:
                w,c=setup(e,spec,definition,fixture,sources)
                def transport(url,key,wire,timeout):
                    v=sample(json.loads(wire['messages'][1]['content']))
                    return {'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[{'id':'offline','type':'function','function':{'name':'submit_review','arguments':json.dumps(v)}}]}}]}
                a=DeepSeekAdapter(LLMConfig('OFFLINE',base_url=definition['provider_endpoint'],max_calls=1,max_output_tokens=4096),transport)
                w.runtime.validate_with_llm(w.tokens['interaction'],c,a)
                req=a.records[0];sizes.append(len(json.dumps(req['messages'],ensure_ascii=False)))
                assert all(x['source_id'] not in json.dumps(req['messages'],ensure_ascii=False) for x in plan['cases'])
                e.emit('scripted_request',**req);e.capture(w.h,'final')
            finally:e.close()
        manifest={'status':'PREPARED_FOR_SIX_CALL_IDENTIFICATION','source_sha256':hashes,'maximum_message_chars':max(sizes),'local_char_limit':16000,
            'planned_calls':6,'max_output_tokens':4096,'external_model_calls':0,'scripted_calls':6,
            'independent_review':'NOT_REVIEWED_NOT_CLAIMED','artifact_sha256':{p.name:sha(p) for p in PACK.iterdir() if p.is_file()}}
        assert max(sizes)<=16000
        write(PACK/'manifest.json',manifest);print(json.dumps(manifest,ensure_ascii=False,indent=2));return
    prepared=read(PACK/'manifest.json')
    for name,h in prepared['source_sha256'].items():
        if sha(REPO/name)!=h:raise ContractError('FrozenSourceMismatch')
    for name,h in prepared['artifact_sha256'].items():
        if sha(PACK/name)!=h:raise ContractError('PreparedEvidenceMismatch')
    original=load_config(REPO)
    if original.model!='deepseek-flash':raise ValueError('FrozenModelMismatch')
    config=replace(original,base_url=definition['provider_endpoint'],max_calls=6,max_output_tokens=4096,timeout_seconds=60)
    if not config.api_key:raise ValueError('MissingConfiguredKey')
    RUN.mkdir(parents=True,exist_ok=False)
    write(RUN/'manifest.json',{'started_at':datetime.now(timezone.utc).isoformat(),'source_sha256':hashes,'package_sha256':sha(PACK/'manifest.json'),
        'config':config.public(),'maximum_calls':6,'retries':0,'automatic_additional_batches':False,'scope':plan['scope']})
    a=DeepSeekAdapter(config);rows=[];consecutive=0;stop=None
    for spec in plan['cases']:
        row={'id':spec['id'],'source_id':spec['source_id'],'author_expected':spec['author_expected'],'execution':'NOT_RUN'}
        if stop is None:
            e=EvidenceRecorder(RUN/(spec['id']+'.jsonl'));start=len(a.records)
            try:
                w,c=setup(e,spec,definition,fixture,sources)
                row['candidate_digest']=digest(c)
                review=w.runtime.validate_with_llm(w.tokens['interaction'],c,a)
                row.update(execution='COMPLETED',accepted_status=review.status,review=json.loads(review.details_json));consecutive=0
            except (ModelFailure,ContractError) as exc:
                row.update(execution='EXECUTION_FAILED',failure_type=type(exc).__name__,reason=str(exc));consecutive+=1
                if consecutive>=3:stop='THREE_CONSECUTIVE_EXECUTION_FAILURES'
            finally:
                for record in a.records[start:]:e.emit('model_execution',**record)
                w.e.capture(w.h,'final');e.close()
                write(RUN/'adapter-records.json',a.records)
            print(json.dumps({'id':spec['id'],'calls':len(a.records),'execution':row['execution'],'accepted_status':row.get('accepted_status'),'reason':row.get('reason')},ensure_ascii=False),flush=True)
        rows.append(row);write(RUN/'results.json',rows)
    summary={'scope':plan['scope'],'planned':6,'external_model_calls':len(a.records),'completed':sum(x['execution']=='COMPLETED' for x in rows),
        'execution_failed':sum(x['execution']=='EXECUTION_FAILED' for x in rows),'not_run':sum(x['execution']=='NOT_RUN' for x in rows),
        'stop_reason':stop,'automatic_additional_batches':False,'A2':'DENIED','E1':'INCONCLUSIVE','full_cases_completed':9,'gate_E':'OPEN','gate_F':'OPEN',
        'completed_at':datetime.now(timezone.utc).isoformat(),'artifact_sha256':{p.name:sha(p) for p in RUN.iterdir() if p.is_file()}}
    write(RUN/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
