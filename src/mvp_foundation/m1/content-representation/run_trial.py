"""Bounded real vision calls using existing credentials; responses never overwrite reference."""
import argparse
import base64
import hashlib
import json
import mimetypes
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import httpx
from jsonschema import Draft202012Validator
from verify import inspect

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]

def config():
    values={}
    env=REPO/'.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k,v=line.split('=',1);values[k.strip()]=v.strip().strip('"').strip("'")
    values.update(os.environ)
    return values

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cases',nargs='*');args=parser.parse_args()
    cfg=config();key=cfg.get('DEERMIND_LLM_API_KEY');base=cfg.get('DEERMIND_LLM_BASE_URL','').rstrip('/');model=cfg.get('DEERMIND_LLM_MODEL','')
    if not key or not base or not model:raise SystemExit('Model configuration incomplete; no calls made.')
    if base!='https://api.deepseek.com':raise SystemExit('This reviewed runner only sends to the configured official DeepSeek endpoint. Review a different provider before sending.')
    reference=json.loads(ROOT.joinpath('reference.json').read_text(encoding='utf-8'));schema=json.loads(ROOT.joinpath('extraction-schema.json').read_text(encoding='utf-8'));plan=json.loads(ROOT.joinpath('trial-plan.json').read_text(encoding='utf-8'))
    selected=[c for c in reference['cases'] if not args.cases or c['id'] in args.cases]
    if not selected or len(selected)>plan['maxCalls']:raise SystemExit('Invalid case selection')
    run=ROOT/'runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');run.mkdir(parents=True,exist_ok=False)
    def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save(run/'manifest.json',dict(model=model,baseUrl=base,plan=plan,cases=[c['id'] for c in selected],inputHashes={name:hashlib.sha256(ROOT.joinpath(name).read_bytes()).hexdigest() for name in ['schema.json','extraction-schema.json','reference.json','extraction-rules.txt','trial-plan.json']},referenceDataSent=False))
    rules=ROOT.joinpath('extraction-rules.txt').read_text(encoding='utf-8')
    def perform(case):
        folder=run/case['id'];folder.mkdir();sources=[s for s in reference['sources'] if s['printedPage'] in case['pages']]
        prompt=json.dumps(dict(caseId=case['id'],scope=case['scope'],pages=[{'id':s['id'],'printedPage':s['printedPage']} for s in sources],outputSchema=schema,catalog=reference['definitions']),ensure_ascii=False,separators=(',',':'))
        parts=[dict(type='text',text=prompt)]
        for s in sources:
            file=ROOT/s['file'];mime=mimetypes.guess_type(file.name)[0]
            parts.extend([dict(type='text',text='书页 '+s['id']),dict(type='image_url',image_url=dict(url=f'data:{mime};base64,'+base64.b64encode(file.read_bytes()).decode('ascii'),detail='high'))])
        payload=dict(model=model,messages=[dict(role='system',content=rules),dict(role='user',content=parts)],response_format=dict(type='json_object'),thinking=dict(type='disabled'),temperature=plan['temperature'],max_tokens=plan['maxOutputTokensPerCall'])
        save(folder/'request.json',dict(system=rules,prompt=prompt,images=[dict(file=s['file'],sha256=s['sha256']) for s in sources],parameters={k:v for k,v in payload.items() if k!='messages'},logicalPayloadSha256=hashlib.sha256(json.dumps(payload,ensure_ascii=False).encode()).hexdigest()))
        start=time.monotonic();record=dict(caseId=case['id'],status='not_started')
        try:
            with httpx.Client(timeout=plan['timeoutSeconds'],follow_redirects=False) as client:
                result=client.post(base+'/chat/completions',headers={'Authorization':'Bearer '+key},json=payload)
            record['httpStatus']=result.status_code
            if result.status_code!=200:
                record.update(status='api_error',error=result.text[:2000].replace(key,'[REDACTED]'));return record
            response=result.json();choice=response['choices'][0];record.update(usage=response.get('usage'),returnedModel=response.get('model'),finishReason=choice.get('finish_reason'))
            # Store answer, finish reason and usage, excluding credentials and private reasoning fields.
            text=choice.get('message',{}).get('content','');(folder/'answer.txt').write_text(text or '',encoding='utf-8')
            if choice.get('finish_reason')!='stop':record.update(status='incomplete_output');return record
            try:output=json.loads(text)
            except (TypeError,json.JSONDecodeError) as exc:record.update(status='invalid_json',error=str(exc));return record
            save(folder/'extracted.json',output)
            issues=[f'{list(e.absolute_path)}: {e.message}' for e in Draft202012Validator(schema).iter_errors(output)]
            if issues:record.update(status='schema_error',issues=issues[:30]);return record
            combined=dict(reference,status='llm_candidate',id=case['id']+'-LLM',definitions=reference['definitions']+output['newDefinitions'],instances=output['instances'],elements=output['elements'],cases=[dict(case,taskId=output['taskId'],solutionIds=output['solutionIds'],checks=[],notes=output['uncertainties'])])
            issues=inspect(combined)
            if issues:record.update(status='relation_or_value_error',issues=issues);return record
            save(folder/'view.json',combined);record.update(status='ready_for_semantic_review',uncertainties=output['uncertainties']);return record
        except ImportError as exc:record.update(status='local_setup_error',error=str(exc),apiRequestSent=False);return record
        except httpx.HTTPError as exc:record.update(status='transport_error',error=type(exc).__name__);return record
        except (KeyError,ValueError) as exc:record.update(status='response_error',error=str(exc));return record
        finally:
            record['elapsedSeconds']=round(time.monotonic()-start,2);save(folder/'result.json',record);print(json.dumps(record,ensure_ascii=False),flush=True)
    # Probe the configured image endpoint once before dispatching the remaining batch.
    records=[perform(selected[0])]
    if records[0]['status']!='local_setup_error' and records[0].get('httpStatus') not in [400,401,403,404,415,422]:
        with ThreadPoolExecutor(max_workers=plan['maxParallel']) as pool:records.extend(pool.map(perform,selected[1:]))
    save(run/'summary.json',dict(status='executed_not_yet_semantically_reviewed',records=records,notRun=[c['id'] for c in selected if c['id'] not in [r['caseId'] for r in records]]));print('Run directory: '+str(run),flush=True)

if __name__=='__main__':main()
