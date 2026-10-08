"""Explicit mechanical fixtures; never imported by the real model adapter."""
from copy import deepcopy
from .common import Rejected
from .protocols import RULES


class ScriptedModel:
    mode='scripted-mechanism'
    def __init__(self,policy='NoIntervention'):
        self.policy=policy;self.fail_next=None;self.review_verdict='PASS';self.calls=[]

    def complete(self,system,context,schema,purpose,category='base'):
        self.calls.append(purpose)
        if purpose==self.fail_next:
            self.fail_next=None;raise Rejected('InjectedEvaluationFailure')
        if purpose.startswith('Review:'):
            p=purpose.split(':',1)[1]
            names=[v['properties']['rule_id']['const'] for v in schema['properties']['checks'].get('prefixItems',[])] or list(RULES[p])
            output={'verdict':self.review_verdict,'checks':[{'rule_id':k,'verdict':self.review_verdict,'reason':'固定机制夹具意见，不证明语义正确','source_ids':[]} for k in names]}
        elif purpose=='Observation':
            output={'summary':'固定机制夹具观察','work_steps':[],'request_interpretation':'机制测试输入',
                    'current_purpose':context['current_activity'],'uncertainties':[],'source_ids':[context['current_input_id']]}
            if 'current_purpose' not in schema['properties']:output.pop('current_purpose')
        elif purpose=='Evidence':
            output={'items':[{'claim_id':c['id'],'relation':'NonInformative','interpretation':'固定评价夹具，不是真实能力判断',
                'observation_ids':[context['observations'][0]['id']],'source_ids':[context['current_input_id']],
                'assistance_ids':[a['id'] for a in context['assistance']], 'coverage':context['assistance_coverage'],
                'assistance_relevance':'仅验证来源传递','dependencies_explanation':'显式测试模式'} for c in context['claims']]}
        elif purpose=='Belief':
            output={'items':[{'claim_id':c['id'],'disposition':'REVISE','assessment_kind':'UNKNOWN','assessment':'固定未知夹具',
                'uncertainty':'这是机制测试','epistemic_status':['FixtureOnly'],'evidence_ids':[e['id'] for e in context['evidence']],
                'conflicts':[],'rationale':'固定夹具，不计为真实评价'} for c in context['claims']]}
        else:
            action=self.policy
            if action=='Control' and context['current_activity']=='Teaching':action='Explanation'
            output={'outcome':action if action in ('NoIntervention','Defer') else 'Execute',
                    'action_type':'None' if action in ('NoIntervention','Defer') else action,
                    'blocks':[] if action in ('Control','NoIntervention','Defer') else [{'block_id':'b1','text':'机制测试展示一'},{'block_id':'b2','text':'机制测试展示二'}],
                    'transition':'Teaching' if action=='Control' else 'None','rationale':'固定决策夹具',
                    'reevaluation_condition':'新输入时重新判断' if action=='Defer' else '', 'source_ids':[context['current_input_id']]}
        return deepcopy(output),{'mode':self.mode,'purpose':purpose,'fixture':True}


class FaultWrapper:
    def __init__(self,model):self.model=model;self.mode=model.mode;self.fail_next=None
    def complete(self,*args,**kwargs):
        purpose=args[3]
        if purpose==self.fail_next:
            self.fail_next=None;raise Rejected('InjectedEvaluationFailure')
        return self.model.complete(*args,**kwargs)
