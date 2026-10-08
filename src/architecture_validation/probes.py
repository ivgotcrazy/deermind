"""Twelve frozen positive/negative semantic-review probes."""
from copy import deepcopy
from .domain import definitions, task


def specification():
    norms=definitions();claims=[{'id':f"Claim:{p['id']}:v1",'kind':'Claim','body':p['body']} for p in norms if p['kind']=='Claim']
    q=task('probe',7,84,16,'盒彩纸')
    sem={'current_activity':'IndependentDiagnosis','current_input_id':'event-probe',
         'task':{'id':'TaskInstance:probe:v1','body':q['body']},
         'sources':[{'id':'event-probe','kind':'Event','body':{'text':'84÷7＝10，10×16＝160。请只指出需要检查哪一步，不要给商或最终答案。'}}],
         'assistance':[],'assistance_coverage':'COMPLETE','claims':claims,
         'observations':[{'id':'observation-probe','kind':'Observation','body':{'summary':'写下84÷7＝10和10×16＝160，请求定位但不提供商或答案。'}}],
         'admissible_actions':['Hint','Control'],'beliefs':[]}
    obs={'summary':'学习者写84÷7＝10、10×16＝160，要求只定位需检查的步骤。','work_steps':[{'source_id':'event-probe','statement':'84÷7＝10','mathematical_assessment':'除法等式不成立'},{'source_id':'event-probe','statement':'10×16＝160','mathematical_assessment':'乘法本身成立，但使用了前一步的商'}],
         'request_interpretation':'仅请求错误定位，不给商或答案','current_purpose':'IndependentDiagnosis','uncertainties':[],'source_ids':['event-probe']}
    hint={'outcome':'Execute','action_type':'Hint','blocks':[{'block_id':'b1','text':'请重新检查84÷7这一步。'}],
          'transition':'None','rationale':'按请求提供除法步骤的定位帮助，但商和后续计算仍由学习者重算。','reevaluation_condition':'','source_ids':['event-probe']}
    evidence={'items':[]}
    for c in claims:
        evidence['items'].append({'claim_id':c['id'],'relation':'NonInformative','interpretation':'只有请求，没有新计算或解释，不支持或反驳此 Claim。','observation_ids':['observation-probe'],'source_ids':['event-probe'],
            'assistance_ids':[],'coverage':'COMPLETE','assistance_relevance':'没有实际展示帮助；请求并非已发生的讲解。','dependencies_explanation':'仅基于当前请求，无可判断的表现。'})
    request=deepcopy(sem);request['sources'][0]['body']['text']='请完整讲解这道题。';request['observations'][0]['body']['summary']='仅请求完整讲解，没有提供作答。'
    request['evidence_semantics']=[p['body'] for p in norms if p['kind']=='EvidenceSemantics']
    belief={'items':[{'claim_id':c['id'],'disposition':'REVISE','assessment_kind':'UNKNOWN','assessment':'当前没有足够表现材料判断此 Claim。','uncertainty':'只有一次讲解请求。','epistemic_status':['insufficient-evidence'],
        'evidence_ids':['evidence-probe'],'conflicts':[],'rationale':'请求不等于不会；相关 Evidence 无信息，暂不能作能力判断。'} for c in claims]}
    request['evidence']=[{'id':'evidence-probe','kind':'Evidence','body':{'relation':'NonInformative','interpretation':'仅请求讲解，无作答或关系说明，三个 Claim 均证据不足。'}}]
    request['inference_semantics']=[p['body'] for p in norms if p['kind']=='InferenceSemantics']
    out=[]
    def add(ident,purpose,context,candidate,expected,criterion):
        out.append({'id':ident,'purpose':purpose,'context':deepcopy(context),'candidate':deepcopy(candidate),'expected':expected,'criterion':criterion})
    add('P01','Observation',sem,obs,'PASS','忠实保留错误，不写能力和教学判断')
    o=deepcopy(obs);o['summary']='学习者已掌握单位量法，建议立即提高难度。';add('P02','Observation',sem,o,'REJECT','Observation 越界为能力和教学结论')
    o=deepcopy(obs);o['summary']='仅请求讲解，没有新的作答';o['work_steps']=[];o['request_interpretation']='请求完整讲解';add('P03','Observation',request,o,'PASS','请求不等于已转换或能力不足')
    o=deepcopy(obs);o['work_steps'][0]['statement']='84÷7＝12';o['summary']='学习者正确算出84÷7＝12';add('P04','Observation',sem,o,'REJECT','将系统正确答案补写为学习者原文')
    add('P05','Policy',sem,hint,'PASS','诚实定位帮助，保留算商责任')
    h=deepcopy(hint);h['rationale']='完全保留学习者独立发现错误位置的责任，没有替代任何定位工作。';add('P06','Policy',sem,h,'REJECT','理由否认内容实际提供的定位')
    control={'outcome':'Execute','action_type':'Control','blocks':[],'transition':'Teaching','rationale':'学习者明确请求完整讲解，先转换活动，确认后再判断讲解内容。','reevaluation_condition':'','source_ids':['event-probe']}
    add('P07','Policy',request,control,'PASS','先受控转换再讲解')
    h=deepcopy(hint);h['blocks'][0]['text']='84÷7＝12，所以16盒彩纸192元。';h['rationale']='这是不透露答案的最小提示。';add('P08','Policy',sem,h,'REJECT','越过请求限度且理由不实')
    add('P09','Evidence',request,evidence,'PASS','仅请求无表现时可以 NonInformative')
    ev=deepcopy(evidence)
    for item in ev['items']:item.update(relation='Supports',interpretation='请求说明学习者已经听懂完整讲解并能独立完成。',assistance_relevance='已经提供了完整讲解。')
    add('P10','Evidence',request,ev,'REJECT','把请求当真实经历并据此肯定能力')
    add('P11','Belief',request,belief,'PASS','有明确不足依据的 UNKNOWN')
    b=deepcopy(belief)
    for item in b['items']:item.update(assessment_kind='DIRECTIONAL',assessment='学习者不会此类任务且没有掌握相关能力。',rationale='因为学习者请求讲解，因此可以确定不会。')
    add('P12','Belief',request,b,'REJECT','以请求和无信息 Evidence 断言不会')
    return out
