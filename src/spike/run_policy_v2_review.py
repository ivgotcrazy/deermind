"""Bounded review-only executor. CLI performs offline controls only; no key/config access."""
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch
from foundation.llm import DeepSeekAdapter, LLMConfig, ModelFailure
from foundation.runtime import ContractError
from foundation.structured_output import matches_schema

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
PACKAGE=ROOT/'review-packages/policy-e1-v2-final'

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def digest(path):return sha256(path.read_bytes()).hexdigest()

def verify(package):
    manifest=read(package/'manifest.json')
    for name,h in manifest['source_sha256'].items():
        if digest(REPO/name)!=h:raise ContractError('ReviewSourceHashMismatch')
    for name,h in manifest['artifact_sha256'].items():
        if digest(package/name)!=h:raise ContractError('ReviewArtifactHashMismatch')
    requests=read(package/'requests.json')
    if len(requests)!=36 or manifest['proposed_call_cap']!=36:raise ContractError('ReviewBudgetMismatch')
    if len({(r['case_id'],r['stage']) for r in requests})!=36:raise ContractError('DuplicateReviewRequest')
    return requests

def execute(package,adapter,directory):
    requests=verify(package)
    # The caller supplies an adapter; do not allow its internal retries to exceed the package cap.
    if adapter.config.public()['retries']!=0 or adapter.records or adapter.config.max_calls!=36 or adapter.config.base_url!='https://api.deepseek.com/beta':
        raise ContractError('ReviewAdapterBudgetMismatch')
    directory.mkdir(parents=True,exist_ok=False)
    rows=[];failures=0;stop=None
    for request in requests:
        row={'case_id':request['case_id'],'stage':request['stage'],'status':'NOT_RUN'}
        if stop is None:
            try:
                output,call=adapter.complete(request['messages'],'FixedPolicyReview:'+request['stage'],output_contract=request['output_contract'])
                if not matches_schema(output,request['output_contract']['parameters']):raise ContractError('ReviewOutputSchemaMismatch')
                if request['stage']=='utility':
                    scores=output['scores'];required={'grounding','responsiveness','responsibility_cost','consistency'}
                    if len(scores)!=4 or {x['id'] for x in scores}!=required:raise ContractError('ReviewRubricIncomplete')
                    status='FAIL' if any(x['status']=='FAIL' for x in scores) else 'UNRESOLVED' if any(x['status']=='UNRESOLVED' for x in scores) else 'PASS'
                else:status=output['status']
                row.update(status='COMPLETED',semantic_or_utility_status=status,output=output,model_call=call)
                failures=0
            except (ModelFailure,ContractError) as exc:
                row.update(status='EXECUTION_FAILED',failure_type=type(exc).__name__,reason=str(exc));failures+=1
                if failures>=3:stop='THREE_CONSECUTIVE_EXECUTION_FAILURES'
            finally:
                write(directory/'adapter-records.json',adapter.records)
        rows.append(row)
        write(directory/'results.json',rows)
    summary={'scope':'fixed review only, no generation/commit/effect','requests':len(requests),
        'model_calls':len(adapter.records),'completed':sum(r['status']=='COMPLETED' for r in rows),
        'execution_failed':sum(r['status']=='EXECUTION_FAILED' for r in rows),
        'not_run':sum(r['status']=='NOT_RUN' for r in rows),'stop_reason':stop,
        'assumption_result':'UNCHANGED','labels_loaded_by_executor':False}
    write(directory/'summary.json',summary)
    return summary

def main():
    destination=ROOT/'runs/policy-v2-review-offline-v3'
    destination.mkdir(parents=True,exist_ok=False)
    def transport(url,headers,payload,timeout):
        tool=payload['tools'][0]['function']['name']
        output=({'status':'UNRESOLVED','rationale':'SCRIPTED TRANSPORT CONTROL, NOT A SEMANTIC JUDGMENT.'}
            if tool=='submit_review' else {'scores':[{'id':k,'status':'UNRESOLVED','reason':'SCRIPTED TRANSPORT CONTROL.'}
                for k in ('grounding','responsiveness','responsibility_cost','consistency')]})
        return {'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[
            {'id':'offline','type':'function','function':{'name':tool,'arguments':json.dumps(output)}}]}}]}
    config=LLMConfig('OFFLINE-NONSECRET-PLACEHOLDER',base_url='https://api.deepseek.com/beta',max_calls=36)
    network=[]
    def block(*args,**kwargs):network.append(True);raise RuntimeError('NetworkDisabled')
    with patch('socket.create_connection',block),patch('socket.socket.connect',block):
        complete=execute(PACKAGE,DeepSeekAdapter(config,transport),destination/'complete')
        def invalid(*args,**kwargs):return {'choices':[]}
        stopped=execute(PACKAGE,DeepSeekAdapter(config,invalid),destination/'stop-control')
    assert complete['completed']==36 and complete['not_run']==0
    assert stopped['execution_failed']==3 and stopped['not_run']==33 and stopped['model_calls']==3
    assert not network
    result={'status':'PASS','external_model_calls':0,'scripted_calls':39,
        'prepared_requests_checked':36,'complete_control':complete,'stop_control':stopped,
        'meaning':'Only request wiring, schema accounting and stop behavior validated; injected UNRESOLVED is not semantic evidence.',
        'package_manifest_sha256':digest(PACKAGE/'manifest.json'),
        'executor_sha256':digest(Path(__file__)),
        'artifact_sha256':{p.relative_to(destination).as_posix():digest(p) for p in destination.rglob('*') if p.is_file()}}
    write(destination/'summary.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
