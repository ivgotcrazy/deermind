"""Two-stage bounded trial. Author-reviewed content is immutable during mapping."""
import argparse
import base64
import copy
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import httpx
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from run_trial import config

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def digest(data):return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def errors(schema,data):return [f'{list(e.absolute_path)}: {e.message}' for e in Draft202012Validator(schema).iter_errors(data)]

def content_errors(case,data):
    found=errors(read(ROOT/(case['id']+'-schema.json')),data)
    if found:return found
    for task in data['tasks']:
        parts=task['question']+task['knowledge']+task['teachingAids']+[p for s in task['solutions'] for p in s['content']]
        for part in parts:
            for b in part['blocks']:
                if b['type']=='chart':
                    if any(len(s['values'])!=len(b['categories']) for s in b['series']):found.append('chart: category/series length')
                    if b['chartType']=='pie' and len(b.get('colors',[]))!=len(b['categories']):found.append('pie: missing category colors')
                    if b['chartType']!='pie' and ('axis' not in b or b['axis']['max']<=b['axis']['min']):found.append('chart: missing/invalid axis')
                    if b['cohortRelation']=='second_subset_of_first' and b['stacked']:found.append('chart: overlapping cohorts stacked')
                if b['type']=='table':
                    for row in b['rows']:
                        if len(row)!=len(b['headers']):found.append('table: row width')
                        for cell in row:
                            if (cell['state']=='provided')!=(cell['value'] is not None):found.append('table: state/value mismatch')
    return found

def compile_graph(case,content,mapping,catalog):
    found=errors(read(ROOT/'mapping-schema.json'),mapping)
    if found:raise ValueError('; '.join(found))
    defs={d['id']:d for d in catalog};tasks=mapping['tasks']
    if sorted(t['taskIndex'] for t in tasks)!=list(range(len(content['tasks']))):raise ValueError('Task mapping must cover exactly the input tasks')
    instances=[];elements=[];bindings=[];pending=[]
    def match(m,kind):
        mid=m['catalogId']
        if mid is None:
            if not m['unmatchedProposal']:raise ValueError('Unmatched mapping needs an explicit proposal')
            pending.append(m);return None
        if m['unmatchedProposal'] is not None or defs.get(mid,{}).get('kind')!=kind:raise ValueError('Invalid catalog choice/type')
        return mid
    def attach(owner,role,parts):
        refs=[]
        for j,p in enumerate(parts):
            region=case['regions'][p['regionIndex']];eid=f'{owner}/{role}/{j}'
            elements.append(dict(id=eid,owner=owner,role=role,origin='reviewed_source_extraction',source=dict(page=region['page'],pixelBox=region['pixelBox'],sourceSha256=region['originalSha256'],cropSha256=region['sha256']),blocks=copy.deepcopy(p['blocks'])))
            refs.append(eid)
        return refs
    for mapped in sorted(tasks,key=lambda t:t['taskIndex']):
        i=mapped['taskIndex'];task=content['tasks'][i];tid=f"R2-{case['id']}-T{i}";template=match(mapped['taskMatch'],'TaskTemplate')
        if sorted(s['solutionIndex'] for s in mapped['solutions'])!=list(range(len(task['solutions']))):raise ValueError('Solution mappings do not match source solutions')
        if sorted(k['knowledgeIndex'] for k in mapped['knowledge'])!=list(range(len(task['knowledge']))):raise ValueError('Knowledge mappings do not match extracted statements')
        instances.append(dict(id=tid,kind='TaskInstance',templateId=template,contentRefs=attach(tid,'question',task['question'])))
        attach(tid,'teaching_aid',task['teachingAids'])
        for sm in sorted(mapped['solutions'],key=lambda s:s['solutionIndex']):
            j=sm['solutionIndex'];sid=f'{tid}-S{j}';method=match(sm['match'],'SolutionTemplate')
            if method and template and method not in defs[template]['solutionIds']:raise ValueError('Solution not permitted by selected task template')
            instances.append(dict(id=sid,kind='SolutionInstance',templateId=method,taskInstanceId=tid,origin='textbook',contentRefs=attach(sid,'solution',task['solutions'][j]['content'])))
        for km in mapped['knowledge']:
            j=km['knowledgeIndex'];kid=match(km['match'],'KnowledgeComponent');sourceId=f'{tid}-KSource{j}'
            attach(sourceId,'knowledge',[task['knowledge'][j]])
            bindings.append(dict(sourceId=sourceId,kcId=kid,status='source_statement_mapping_not_task_dependency'))
    return dict(caseId=case['id'],status='pending_mapping' if pending else 'linked_pending_semantic_review',contentHash=digest(content),instances=instances,elements=elements,knowledgeBindings=bindings,pending=pending,definitions=catalog)

def approved_content(folder,case):
    review=read(folder/'content-review.json');data=read(folder/'reviewed-content.json')
    if review.get('decision')!='accept_for_mapping' or review.get('reviewedContentHash')!=digest(data):raise ValueError('Author review missing or stale')
    if content_errors(case,data):raise ValueError('Reviewed content still violates format')
    return data

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['extract','map']);p.add_argument('--run');args=p.parse_args()
    cfg=config();key=cfg.get('DEERMIND_LLM_API_KEY');base=cfg.get('DEERMIND_LLM_BASE_URL','').rstrip('/');model=cfg.get('DEERMIND_LLM_MODEL')
    if not key or not model or base!='https://api.deepseek.com':raise SystemExit('Expected existing official DeepSeek configuration; no calls made')
    cases=read(ROOT/'cases.json');plan=read(ROOT/'plan.json');catalog=read(ROOT/'catalog.json')
    if args.stage=='extract':
        run=ROOT/'runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');run.mkdir(parents=True,exist_ok=False)
        save(run/'manifest.json',dict(model=model,baseUrl=base,plan=plan,hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in ROOT.iterdir() if f.is_file() and f.suffix in ['.json','.txt','.py']},referenceInstancesSent=False,catalogSentDuringExtraction=False))
        (ROOT/'latest-run.txt').write_text(run.name,encoding='utf-8')
    else:
        if not args.run:raise SystemExit('--run required for mapping')
        run=(ROOT/'runs'/args.run).resolve()
        if run.parent!=(ROOT/'runs').resolve():raise SystemExit('Invalid run path')
        for case in cases:approved_content(run/case['id'],case)
    rules=(ROOT/(args.stage+'-rules.txt')).read_text(encoding='utf-8')
    def perform(case):
        folder=run/case['id'];folder.mkdir(exist_ok=True)
        if (folder/(args.stage+'-result.json')).exists():raise RuntimeError('Stage already executed; refusing to overwrite')
        schema=read(ROOT/(case['id']+'-schema.json' if args.stage=='extract' else 'mapping-schema.json'))
        if args.stage=='extract':
            prompt=dict(scope=case['scope'],regions=[dict(index=r['index'],page=r['page']) for r in case['regions']],outputSchema=schema)
        else:
            content=approved_content(folder,case);prompt=dict(content=content,catalog=catalog,outputSchema=schema)
        text=json.dumps(prompt,ensure_ascii=False,separators=(',',':'));parts=[dict(type='text',text=text)]
        if args.stage=='extract':
            for r in case['regions']:
                data=base64.b64encode((ROOT/r['file']).read_bytes()).decode()
                parts.extend([dict(type='text',text=f"regionIndex={r['index']}, 教材第{r['page']}页"),dict(type='image_url',image_url=dict(url='data:image/png;base64,'+data,detail='high'))])
        payload=dict(model=model,messages=[dict(role='system',content=rules),dict(role='user',content=parts)],response_format=dict(type='json_object'),thinking=dict(type='disabled'),temperature=0,max_tokens=plan['maxOutputTokens'])
        save(folder/(args.stage+'-request.json'),dict(system=rules,prompt=prompt,images=case['regions'] if args.stage=='extract' else [],parameters={k:v for k,v in payload.items() if k!='messages'},logicalPayloadHash=digest(payload)))
        attempts=[];record=dict(caseId=case['id'],stage=args.stage)
        for attempt in range(plan['maxTransportRetriesPerCall']+1):
            start=time.monotonic()
            try:
                with httpx.Client(timeout=plan['timeoutSeconds'],follow_redirects=False) as client:
                    response=client.post(base+'/chat/completions',headers={'Authorization':'Bearer '+key},json=payload)
                attempts.append(dict(number=attempt+1,status=response.status_code,elapsedSeconds=round(time.monotonic()-start,2)))
                record['httpStatus']=response.status_code
                if response.status_code!=200:
                    record.update(status='api_error',error=response.text[:1500].replace(key,'[REDACTED]'));break
                data=response.json();choice=data['choices'][0];answer=choice.get('message',{}).get('content','') or ''
                record.update(usage=data.get('usage'),finishReason=choice.get('finish_reason'),returnedModel=data.get('model'))
                (folder/(args.stage+'-answer.txt')).write_text(answer,encoding='utf-8')
                if choice.get('finish_reason')!='stop':record['status']='incomplete_output';break
                try:output=json.loads(answer)
                except json.JSONDecodeError as exc:record.update(status='invalid_json',error=str(exc));break
                save(folder/(args.stage+'-output.json'),output)
                issues=content_errors(case,output) if args.stage=='extract' else errors(schema,output)
                if issues:record.update(status='schema_or_invariant_error',issues=issues);break
                if args.stage=='map':
                    try:save(folder/'graph.json',compile_graph(case,content,output,catalog))
                    except ValueError as exc:record.update(status='mapping_relation_error',error=str(exc));break
                record['status']='ready_for_author_review';break
            except httpx.HTTPError as exc:
                attempts.append(dict(number=attempt+1,status='transport_error',error=type(exc).__name__,elapsedSeconds=round(time.monotonic()-start,2)));record['status']='transport_error'
            except (ValueError,KeyError,ImportError) as exc:record.update(status='local_or_response_error',error=str(exc));break
        record['attempts']=attempts;save(folder/(args.stage+'-result.json'),record);print(json.dumps(record,ensure_ascii=False),flush=True);return record
    with ThreadPoolExecutor(max_workers=plan['maxParallel']) as pool:records=list(pool.map(perform,cases))
    save(run/(args.stage+'-summary.json'),records);print('RUN '+run.name,flush=True)

if __name__=='__main__':main()
