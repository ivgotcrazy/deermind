"""Author review revision: neutral synthetic IDs and explicit review strata. Offline only."""
import copy,json,math
from hashlib import sha256
from pathlib import Path
from foundation.structured_output import matches_schema
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    old=ROOT/'review-packages/policy-e1-v2-final';new=ROOT/'review-packages/policy-e1-v2-reviewed'
    previous=read(old/'manifest.json')
    for name,h in previous['artifact_sha256'].items():assert sha(old/name)==h
    cases=read(old/'cases.json');labels=read(old/'author-expectations.json');definition=read(ROOT/'protocols/policy-e1-v2.json')
    changes=[]
    for index,c in enumerate(cases[:14],1):
        maps={json.dumps(r['ref'],sort_keys=True):dict(r['ref'],identity=f'R{index:02d}-{j:02d}',revision='review-v3')
            for j,r in enumerate(c['context'],1) if r['kind']!='ActionSemantic'}
        def neutral(value):
            if isinstance(value,dict):
                if set(value)=={'space','identity','revision'}:return maps.get(json.dumps(value,sort_keys=True),value)
                return {k:neutral(v) for k,v in value.items()}
            if isinstance(value,list):return [neutral(v) for v in value]
            return value
        c['context']=neutral(c['context']);c['candidate']=neutral(c['candidate'])
        p=c['candidate'];identity=c['id']
        if identity=='uncertainty_not_required':
            p['rationale']='当前可核对的除法失配足以说明本次自行检查的依据；不额外猜测未观察到的错误。预计可促进查错，但可能打断学习者原有检查过程；具体定位和重算仍由学习者完成。'
        if identity=='same_action_own_reason':
            p['uncertainty']='仅凭这次作答不能确定错误原因；完整讲解后的照用不能区分独立掌握与依赖示范，需要后续未获同样帮助的新机会提供材料。当前选择仍基于讲解请求和已生效教学活动。'
        if identity=='future_as_actual':
            c['context'].append({'ref':{'space':'fact','identity':f'R{index:02d}-11','revision':'review-v3'},'kind':'ExecutionStatus',
                'content':{'episode':p['episode'],'candidate_action_dispatched':False,'earlier_display_of_this_hint':False,'source':'TRUSTED_SCRIPTED_EXECUTION_FIXTURE'}})
            p['context_refs'].append(c['context'][-1]['ref'])
        if identity=='missing_review_material':
            for r in c['context']:
                if r['kind']=='ReviewMaterialAvailability':
                    r['content']={'missing':'The original work was available when the candidate was authored but is withheld from this review input. Its contents cannot be reconstructed here. This record does not establish whether the candidate describes it correctly.'}
        if identity=='upstream_not_authority':
            c['review_stratum']='MIXED_AUTHORITY_NEGATIVE_NOT_PURE_SEMANTIC'
        else:c['review_stratum']='AUTHOR_LABELLED_SEMANTIC_PROBE'
        labels[index-1]['review_status']='AUTHOR_SECOND_PASS_NOT_INDEPENDENT'
        labels[index-1]['review_stratum']=c['review_stratum']
        changes.append({'id':identity,'neutral_source_refs':True,'semantic_expected_unchanged':True,
            'focused_edit':identity in ('uncertainty_not_required','same_action_own_reason','future_as_actual','missing_review_material'),
            'interpretation':'Only listed utility dimensions are labelled; PASS is not a full utility endorsement.'})
    for c in cases[14:]:c['review_stratum']='HISTORICAL_DISPUTE_NO_NEW_LABEL'
    requests=[]
    for c in cases:
        assert matches_schema(c['candidate'],definition['output_contracts']['generation']['parameters'])
        refs=[r['ref'] for r in c['context']]
        assert all(r in refs for r in c['candidate']['context_refs'])
        for stage,key,contract in [('semantic','validation_system','validation'),('utility','utility_system','utility')]:
            body={'context':c['context'],'candidate':c['candidate']}
            if stage=='utility':body['rubric']=definition['utility_rubric']
            messages=[{'role':'system','content':definition[key]},{'role':'user','content':json.dumps(body,ensure_ascii=False)}]
            if c['origin'].startswith('AUTHOR'):
                assert all(x['id'] not in json.dumps(messages,ensure_ascii=False) for x in cases[:14])
            requests.append({'case_id':c['id'],'stage':stage,'messages':messages,'output_contract':definition['output_contracts'][contract]})
    # Preserve all four historical contexts and candidates exactly, despite adding audit-only strata outside messages.
    originals=read(old/'cases.json')
    for c,o in zip(cases[14:],originals[14:],strict=True):assert c['candidate']==o['candidate'] and c['context']==o['context']
    budget=[]
    for r in requests:
        body={'model':'deepseek-flash','messages':r['messages'],'stream':False,'thinking':{'type':'disabled'},'temperature':0,
            'max_tokens':2048,'tools':[{'type':'function','function':{**r['output_contract'],'strict':True}}],
            'tool_choice':{'type':'function','function':{'name':r['output_contract']['name']}}}
        text=json.dumps(body,ensure_ascii=False)
        approx=math.ceil(sum(0.3 if ord(ch)<128 else 0.6 for ch in text))
        budget.append({'case_id':r['case_id'],'stage':r['stage'],'message_chars':len(json.dumps(r['messages'],ensure_ascii=False)),
            'request_utf8_bytes':len(text.encode()),'rough_token_estimate':approx,'estimate_caveat':'Non-ASCII treated as Chinese for planning; not tokenizer count or hard bound.'})
    new.mkdir(parents=True,exist_ok=False)
    for name,value in [('cases.json',cases),('author-expectations.json',labels),('requests.json',requests),('author-review.json',changes),('input-budget.json',budget)]:write(new/name,value)
    sources=[Path(__file__),old/'manifest.json',old/'cases.json',old/'author-expectations.json',ROOT/'protocols/policy-e1-v2.json',ROOT/'run_policy_v2_review.py']
    manifest={**previous,'status':'READY_FOR_EXPLORATORY_AUTHOR_LABEL_AGREEMENT_ONLY',
        'scope':'Fixed review-only exploration; author labels are not independent truth; no Gate or full E1 acceptance',
        'independent_review':'NOT_REVIEWED_NOT_CLAIMED','author_review':'SECOND_PASS_COMPLETE',
        'maximum_message_chars':max(x['message_chars'] for x in budget),
        'maximum_request_utf8_bytes_including_contract':max(x['request_utf8_bytes'] for x in budget),
        'maximum_rough_token_estimate':max(x['rough_token_estimate'] for x in budget),
        'provider_token_budget':'DOCUMENTED_CAPACITY_PRECHECK_ONLY_USAGE_PENDING',
        'planned_config':{'model':'deepseek-flash','base_url':'https://api.deepseek.com/beta','max_output_tokens':2048,'timeout_seconds':60,'thinking':'disabled','retries':0,'max_calls':36},
        'provider_docs':{'checked_on':'2026-10-06','pricing':'https://api-docs.deepseek.com/quick_start/pricing/','tool_calls':'https://api-docs.deepseek.com/guides/tool_calls/','tokens':'https://api-docs.deepseek.com/quick_start/token_usage/',
            'documented_alias_version':'DeepSeek-V4.1-Flash','context':'1M tokens','maximum_output':'384K tokens','actual_response_identity':'NOT_CALLED'},
        'readiness_remaining':['Independent labels required before claiming independent semantic accuracy; exploratory agreement must remain explicitly author-labelled',
            'Capture actual returned model/system_fingerprint/usage during any future fixed execution; do not equate alias with immutable weights'],
        'source_sha256':{p.relative_to(REPO).as_posix():sha(p) for p in sources},
        'artifact_sha256':{p.name:sha(p) for p in new.iterdir() if p.is_file()}}
    write(new/'manifest.json',manifest)
    print(json.dumps({k:manifest[k] for k in ('status','cases','prepared_requests','maximum_message_chars','maximum_rough_token_estimate','provider_token_budget')},ensure_ascii=False))
if __name__=='__main__':main()
