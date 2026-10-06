"""One explicit, fixed 36-call exploration. No retries or replacement campaign."""
import argparse
from dataclasses import replace
from datetime import datetime,timezone
import json
from pathlib import Path
from foundation.llm import DeepSeekAdapter,load_config
from run_policy_v2_review import execute,verify,read,write,digest
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
PACKAGE=ROOT/'review-packages/policy-e1-v2-reviewed'
DIRECTORY=ROOT/'runs/policy-v2-review-real-v1'

class ProgressAdapter(DeepSeekAdapter):
    def complete(self,*args,**kwargs):
        try:return super().complete(*args,**kwargs)
        finally:print(json.dumps({'calls':len(self.records),'last_status':self.records[-1]['status'] if self.records else 'NO_CALL'},ensure_ascii=False),flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true');args=parser.parse_args()
    verify(PACKAGE);spec=read(PACKAGE/'manifest.json')['planned_config']
    original=load_config(REPO)
    if original.model!=spec['model']:raise ValueError('ConfiguredModelDiffersFromFrozenPlan')
    config=replace(original,base_url=spec['base_url'],max_calls=spec['max_calls'],max_output_tokens=spec['max_output_tokens'],timeout_seconds=spec['timeout_seconds'])
    if not args.run:
        print(json.dumps({'ready':bool(config.api_key) and not DIRECTORY.exists(),'reserved':DIRECTORY.exists(),'config':config.public()},indent=2));return
    if not config.api_key:raise ValueError('MissingConfiguredAPIKey')
    DIRECTORY.mkdir(parents=True,exist_ok=False)
    write(DIRECTORY/'manifest.json',{'schema':'policy-v2-fixed-real-review-v1','started_at':datetime.now(timezone.utc).isoformat(),
        'scope':'Author-labelled exploration of 18 fixed candidates, two reviews each, no generation/commit/effect',
        'package_manifest_sha256':digest(PACKAGE/'manifest.json'),'executor_sha256':digest(ROOT/'run_policy_v2_review.py'),
        'entrypoint_sha256':digest(Path(__file__)),'adapter_sha256':digest(ROOT/'foundation/llm.py'),
        'config':config.public(),'maximum_calls':36,'retries':0,'stop_after_consecutive_execution_failures':3,
        'independent_review':'NOT_REVIEWED_NOT_CLAIMED','automatic_additional_batches':False})
    adapter=ProgressAdapter(config)
    summary=execute(PACKAGE,adapter,DIRECTORY/'execution')
    write(DIRECTORY/'summary.json',{**summary,'completed_at':datetime.now(timezone.utc).isoformat(),
        'external_model_calls':len(adapter.records),'automatic_additional_batches':False,
        'full_cases_completed':9,'A2':'DENIED','E1':'INCONCLUSIVE','gate_E':'OPEN','gate_F':'OPEN',
        'artifact_sha256':{p.relative_to(DIRECTORY).as_posix():digest(p) for p in DIRECTORY.rglob('*') if p.is_file()}})
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
