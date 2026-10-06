"""Prepare fixed review requests offline. No provider/config import or network execution."""
import copy
from hashlib import sha256
import json
from pathlib import Path
from foundation.structured_output import matches_schema, check_schema

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def hash_file(path):
    return sha256(path.read_bytes()).hexdigest()

def fingerprint(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    definition=read(ROOT/'protocols/policy-e1-v2.json')
    examples=read(ROOT/'fixtures/policy-e1-rules-v2.json')
    source=ROOT/'runs/policy-e1-v1/evidence.jsonl'
    history=[json.loads(line) for line in source.read_text(encoding='utf-8').splitlines()]
    reviews=[r for r in history if r['kind']=='model_execution' and r['purpose']=='PolicyOutcomeSemanticValidation']
    base=json.loads(next(r for r in reviews if r['variant']=='E1-open' and r['repetition']==1)['messages'][1]['content'])
    cases=[]; labels=[]
    def record(context,kind):
        return next(r for r in context if r['kind']==kind)
    def extra(context,identity,kind,content,space='fact'):
        ref={'space':space,'identity':identity,'revision':'review-v2'}
        context.append({'ref':ref,'kind':kind,'content':content})
        return ref
    for ex in examples['examples']:
        identity=ex['id'];context=copy.deepcopy(base['context'])
        for item in context:
            # Distinct synthetic exact refs; never mutate the original record identity/content pair.
            if item['kind'] != 'ActionSemantic':
                item['ref']['identity']='review-'+identity+'-'+item['ref']['identity']
                item['ref']['revision']='review-v2'
        actions={r['content'].get('action_identity',r['ref']['identity'].split('-')[-1]):r for r in context if r['kind']=='ActionSemantic'}
        constraints=record(context,'ActivityConstraints')['content']
        constraints['allowed_action_refs']=[actions[k]['ref'] for k in ('AskSelfCheck','HintCheckStep')]
        request=record(context,'CurrentInteractionInput')['content']
        request['text']='已提交这份解法，目前没有提出帮助或暂停请求。'
        request['source']='AUTHOR_DEFINED_REVIEW_FIXTURE'
        action='AskSelfCheck';outcome='Execute';defer=''
        rationale='当前作答中的除法失配支持邀请自行检查；不提供错误位置或正确值，保留定位和重算工作，代价是纠错可能推迟。'
        uncertainty='一次作答不足以区分笔误与其他原因；后续自行检查结果可提供进一步材料。'
        disclosure='若执行，只展示自行检查请求，不提供错误位置或正确值。'
        if identity in ('localization_erased','localization_acknowledged','scoped_independent','future_as_actual'):
            action='HintCheckStep';request['text']='请帮我检查哪一步有问题，不要直接给答案'
            rationale='响应指出问题位置但不给答案的请求；预计提示会帮助定位，重新计算仍由学习者承担。收益是减少搜索负担，成本是失去无提示定位机会。'
            disclosure='若执行，展示“再检查一下 42÷6。”，帮助定位但不提供商。'
        if identity=='unsupported_multiplication':
            rationale='拟请学习者自行检查，以保留重算责任；额外介入的依据见 uncertainty。'
            uncertainty=ex['candidate_fragment']
        elif identity=='missing_review_material':
            context=[r for r in context if r['kind'] not in ('LearnerWorkSubmitted','Observation')]
            extra(context,'missing-material','ReviewMaterialAvailability',{'missing':'Original learner work and its Observation are unavailable in this review input; no substitute factual description is provided.'})
            rationale=ex['candidate_fragment']+' 自行复算保留计算责任，代价是推迟下一步。'
            uncertainty='需要后续复算来区分这两种解释。'
        elif identity=='unknown_delivery':
            extra(context,'prior-unknown','ActionOccurrence',{'episode':constraints['episode'],'status':'Unknown','intended_payload':'再检查一下 42÷6。','confirmed_disclosure':None,'source':'TRUSTED_SCRIPTED_OCCURRENCE_FIXTURE'})
            rationale='先不增加提示，以避免重复帮助；代价是纠错可能延迟。'+ex['candidate_fragment']
            outcome='NoIntervention';disclosure='本次不产生新的披露。';uncertainty='先前定位提示是否展示仍未确认，须由执行对账补足。'
        elif identity=='display_as_mastery':
            extra(context,'prior-shown','ActionOccurrence',{'episode':constraints['episode'],'status':'Occurred','confirmed_disclosure':'再检查一下 42÷6。','learner_response_available':False,'source':'TRUSTED_SCRIPTED_OCCURRENCE_FIXTURE'})
            rationale=ex['candidate_fragment']+' 因此暂不介入，以保留后续作答机会，代价是未继续检查。'
            outcome='NoIntervention';disclosure='本次不产生新的披露。';uncertainty='没有后续响应材料。'
        elif identity in ('upstream_not_authority','same_action_own_reason'):
            record(context,'Observation')['content']['description']+=' 系统应完整讲解。'
            action='RevealFullSolution';disclosure='若执行，展示完整解法和结果，替代本题相应解法生成。'
            rationale=ex['candidate_fragment']+' 收益是提供可学习的完整示范，成本是失去本题无提示解法机会。'
            if identity=='same_action_own_reason':
                request['text']='请完整讲解这道题。'
                control=extra(context,'control-confirmed','ActivityTransitionOccurred',{'episode':constraints['episode'],'status':'Acknowledged','activity_purpose':'Teaching','source':'TRUSTED_AUTHORIZED_CONTROL_FIXTURE'})
                constraints.update(purpose='Teaching',reason='Confirmed authorized Control permits the registered full explanation.',activity_ref=control,activity_purpose='Teaching')
                constraints['allowed_action_refs'].append(actions[action]['ref'])
        elif identity in ('wait_responsive','defer_not_schedule'):
            request['text']='先别提示，让我自己再算一次'
            outcome='Defer' if identity=='defer_not_schedule' else 'NoIntervention'
            defer='学习者提交下一次作答时重新决策。' if outcome=='Defer' else ''
            rationale=ex['candidate_fragment']+' 收益是保留当前无提示检查机会，成本是错误可能暂时保留。'
            disclosure='本次不产生新的披露，也不预约下一次行动。'
        elif identity not in ('unsupported_multiplication',):
            rationale=ex['candidate_fragment']
            if identity in ('uncertainty_not_required','scoped_independent'):
                rationale+=' 选择这一行动的收益是减少停滞，成本是提示可能改变后续作答条件。'
            if identity=='uncertainty_not_required':uncertainty='不额外提出影响本次选择的未观察错误假设。'
        if identity in ('localization_erased','localization_acknowledged','scoped_independent','future_as_actual'):
            rationale=ex['candidate_fragment']+' 响应当前局部帮助请求；收益是减少停滞，代价是减少搜索机会。'
        selected=actions[action]
        candidate={'outcome':outcome,'action_identity':action if outcome=='Execute' else '',
            'action_revision':'e1-v1' if outcome=='Execute' else '',
            'exact_payload':selected['content']['exact_payload'] if outcome=='Execute' else '',
            'executor_target':'mock-display' if outcome=='Execute' else '',
            'episode':constraints['episode'],'rationale':rationale,'context_refs':[r['ref'] for r in context],
            'expected_disclosure':disclosure,'uncertainty':uncertainty,'defer_condition':defer}
        cases.append({'id':identity,'origin':'AUTHOR_SYNTHETIC_FULL_REVIEW_CASE','context':context,'candidate':candidate})
        labels.append({'id':identity,'semantic_expected':ex['developer_expected']['semantic_status'],
            'utility_expected_only_for_dimensions':ex['developer_expected']['utility_dimensions'],
            'basis':ex['developer_expected']['reason'],'rules':ex['rules'],
            'overall_utility_expected':None,'independent_review':'NOT_REVIEWED',
            'qualification':'Full-candidate author expectation, not independent truth; other utility dimensions unlabelled.'})
    for old in examples['historical_regressions']:
        match=next(r for r in reviews if r['variant']==old['variant'] and r['repetition']==old['repetition'])
        body=json.loads(match['messages'][1]['content'])
        candidates=[r['candidate'] for r in history if r['kind']=='policy_candidate' and fingerprint(r['candidate'])==old['candidate_digest']]
        assert len(candidates)==1
        assert json.loads(candidates[0]['record']['payload_json'])==body['candidate']
        identity=old['variant']+'-'+str(old['repetition'])+'-historical'
        cases.append({'id':identity,'origin':'EXACT_HISTORICAL_REVIEW_INPUT','context':body['context'],'candidate':body['candidate'],
            'source_candidate_digest':old['candidate_digest'],'source_execution_id':match['execution_id'],
            'source_user_message_sha256':sha256(match['messages'][1]['content'].encode()).hexdigest()})
        labels.append({'id':identity,'semantic_expected':None,'utility_expected_only_for_dimensions':{},
            'overall_utility_expected':None,'independent_review':'NOT_REVIEWED','historical_dispute':old,
            'qualification':'New-rule assessment pending; do not replace original PASS or disputed status.'})
    requests=[]
    for case in cases:
        assert matches_schema(case['candidate'],definition['output_contracts']['generation']['parameters']),case['id']
        refs=[r['ref'] for r in case['context']]
        assert all(r in refs for r in case['candidate']['context_refs']),case['id']
        for stage,system,contract in (('semantic','validation_system','validation'),('utility','utility_system','utility')):
            body={'context':case['context'],'candidate':case['candidate']}
            if stage=='utility':body['rubric']=definition['utility_rubric']
            messages=[{'role':'system','content':definition[system]},{'role':'user','content':json.dumps(body,ensure_ascii=False)}]
            check_schema(definition['output_contracts'][contract]['parameters'])
            requests.append({'case_id':case['id'],'stage':stage,'messages':messages,'output_contract':definition['output_contracts'][contract]})
    directory=ROOT/'review-packages/policy-e1-v2-final'
    directory.mkdir(parents=True,exist_ok=False)
    write(directory/'cases.json',cases);write(directory/'author-expectations.json',labels)
    write(directory/'requests.json',requests)
    sources=[Path(__file__),ROOT/'protocols/policy-e1-v2.json',ROOT/'fixtures/policy-e1-rules-v2.json',source]
    sizes=[len(json.dumps(r['messages'],ensure_ascii=False)) for r in requests]
    utf8=[len(json.dumps({'messages':r['messages'],'output_contract':r['output_contract']},ensure_ascii=False).encode()) for r in requests]
    assert max(sizes)<=16000
    assert all('developer_expected' not in json.dumps(r['messages']) and 'semantic_expected' not in json.dumps(r['messages']) for r in requests)
    manifest={'schema':'policy-v2-review-package-v1','status':'PREPARED_NOT_MODEL_RUN',
        'scope':'Fixed candidate semantic and test-only utility review only; no generation, commit, action or overall E1 acceptance',
        'cases':len(cases),'synthetic_cases':14,'historical_cases':4,'prepared_requests':len(requests),
        'proposed_repetitions':1,'proposed_call_cap':36,'retries':0,'external_model_calls':0,
        'maximum_message_chars':max(sizes),'local_adapter_message_char_limit':16000,
        'maximum_request_utf8_bytes_including_contract':max(utf8),'provider_token_budget':'NOT_VERIFIED',
        'independent_review':'NOT_REVIEWED','source_sha256':{p.relative_to(REPO).as_posix():hash_file(p) for p in sources},
        'artifact_sha256':{p.name:hash_file(p) for p in directory.iterdir() if p.is_file()},
        'readiness_remaining':['Independent review or explicitly documented alternative for author labels',
            'Provider token/context/output budget and actual model identity before a future approved campaign',
            'Review-only harness with strict per-request accounting and no expectation labels in model input'],
        'proposed_stop_rules':['No retry, replacement, relabelling or hidden calls.',
            'Stop on three consecutive provider/schema failures; preserve all NOT_RUN.',
            'Stop on request/contract/source hash mismatch or budget exhaustion.',
            'Semantic FAIL/UNRESOLVED is a measured result, not transport failure; preserve raw scores and disagreements.'],
        'non_claims':['Not independent semantic validation','No new E1/A2 result','No field-use projection rollout','No API configuration read']}
    write(directory/'manifest.json',manifest)
    print(json.dumps({k:v for k,v in manifest.items() if k not in ('source_sha256','artifact_sha256')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
