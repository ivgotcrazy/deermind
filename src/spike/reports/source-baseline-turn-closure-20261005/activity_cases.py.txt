"""X5 real cognition with scripted Claim-relative Evaluation and mock effects."""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import json
from uuid import uuid4

from .action_cases import ActionWorld
from .actions import exact_ref
from .activity import ActivityRuntime
from .boundary import ContextInput, Protocol, digest
from .cases import seed
from .records import Ref, Role, Space, VersionContext, json_value
from .runtime import Compatibility, ContractError, CurrentResolver, Decision
from .security import AuthorityGrant, DataUseGrant, parameter
from .session import SerialSession

ROOT = Path(__file__).resolve().parents[1]
EXPLANATION = '苹果单价不变，总价与重量成正比。先求每千克的价格：42÷6=7 元/千克。再求 15 千克的总价：7×15=105 元。所以答案是 105 元。原作答中 42÷6=8 的除法结果有误。'


class PathIncomplete(ContractError):
    pass


class ActivityWorld(ActionWorld):
    def __init__(self, evidence):
        self.endpoint = 'https://api.deepseek.com/beta'
        super().__init__(evidence)
        self.control = ActivityRuntime(self.runtime)
        self.sessions = SerialSession(self.runtime)
        self.activity = seed(self.h, Ref(Space.FACT, 'X5-initial-activity', '1'), kind='ActivityState',
            occurrence_key='X5-initial-activity', payload={'activity_purpose':'IndependentDiagnosis',
                'episode':self.episode, 'task_ref':json_value(Ref(Space.CANONICAL,'T-Apple-6-42-15','v1'))})
        self.initial_activity = self.activity
        self.target = seed(self.h, Ref(Space.CANONICAL,'X5-Target','v1'), kind='Target',
            payload={'responsibility':'Independent proportional-reasoning task performance remains the final objective.'})
        self.tasks = tuple(seed(self.h, Ref(Space.CANONICAL,name,'v1'), kind='TaskInstance',
            payload={'question':question, 'task_family':'ProportionalUnitRate', 'given_kg':kg,'given_yuan':yuan,'requested_kg':wanted})
            for name,question,kg,yuan,wanted in [('T-Apple-6-42-15','6kg 苹果 42 元，15kg 多少钱？',6,42,15),
                                               ('T-Apple-10-60-7','10kg 苹果 60 元，7kg 多少钱？',10,60,7)])
        self.claims = {c:seed(self.h,Ref(Space.CANONICAL,'X5-'+c,'v1'),kind='Claim',payload={'meaning':meaning})
            for c,meaning in [('C1','Independent proportional task proficiency'),('C2','Unit-rate strategy selection before help')]}
        self.initial_target = self.h.get(self.target)
        self.initial_fact = self.h.get(self.work)
        self.install_protocol('initial', 'Observation', ROOT/'protocols/observation-smoke-v11.json', ('LearnerWorkSubmitted',))
        self.install_protocol('request', 'Observation', ROOT/'protocols/observation-x5-request-v1.json', ('CurrentInteractionInput',))
        self.install_protocol('new-work', 'Observation', ROOT/'protocols/observation-x5-new-work-v1.json', ('LearnerWorkSubmitted',))
        self.install_protocol('policy', 'PolicyOutcome', ROOT/'protocols/policy-x5-v1.json',
            ('Observation','CurrentInteractionInput','ActivityState','ActivityTransitionOccurred','ActivityConstraints',
             'ActionSemantic','Target','TaskInstance','ActionOccurrence'))
        # Evaluation remains an explicit mechanism fixture; no claim of learned Evidence inference.
        prior = self.protocols['Evidence']
        evidence_protocol = seed(self.h,Ref(Space.CANONICAL,'X5-Evidence-Protocol','v1'),kind='ReasoningProtocol',
            payload={'semantic_source':'SCRIPTED-X5-EVALUATION-FIXTURE'})
        self.protocols['Evidence'] = Protocol(evidence_protocol,'Evidence','Evaluation',
            ('Observation','ActionOccurrence','Claim','TaskInstance','Evidence','LearnerWorkSubmitted'), prior.fields, prior.semantic_rule)
        self.runtime.register_protocol(self.protocols['Evidence'])
        self.h.canonical.add_compatibility_fixture(Compatibility('X5-E-compatible',(evidence_protocol,prior.semantic_rule),'learner-A','learning',Decision.ALLOW))
        self.versions['Evidence'] = VersionContext((evidence_protocol,prior.semantic_rule),compatibility_basis='X5-E-compatible')
        self.security.install_authority(AuthorityGrant('X5-E-reason','evaluation','learning','learner-A',(evidence_protocol.identity,),('reason','validate'),100000))
        self.security.install_data(DataUseGrant('X5-control-data','interaction','learning','learner-A',('ControlEffect',),('execute',),('activity-control',),'run','internal',100000))
        self.stages = []
        self.pending_snapshots = {}

    def allow_reads(self):
        super().allow_reads()
        records = [r for space in Space for r in self.h.history_for(space).records('learner-A')]
        self.security.install_data(DataUseGrant('X5-model-'+uuid4().hex,'interaction','learning','learner-A',
            tuple({r.kind for r in records}),('read',),(self.endpoint,),'run','internal',100000))

    def install_protocol(self, name, kind, path, inputs):
        definition = json.loads(path.read_text(encoding='utf-8'))
        ref = seed(self.h,Ref(Space.CANONICAL,'X5-'+name+'-Protocol','v1'),kind='ReasoningProtocol',payload=definition)
        rule = seed(self.h,Ref(Space.CANONICAL,'X5-'+name+'-Rules','v1'),kind='SemanticValidationRules',payload={
            'format':definition.get('validation_format','legacy-v1'), 'system':definition['validation_system'],
            'criteria':definition.get('criteria',[])})
        protocol = Protocol(ref,kind,'Interaction',inputs,tuple(tuple(f) for f in definition.get('fields',[['description','string']])),rule,self.endpoint)
        self.runtime.register_protocol(protocol)
        self.protocols[name]=protocol
        self.h.canonical.add_compatibility_fixture(Compatibility('X5-'+name,(ref,rule),'learner-A','learning',Decision.ALLOW))
        self.versions[name]=VersionContext((ref,rule),compatibility_basis='X5-'+name)
        self.security.install_authority(AuthorityGrant('X5-reason-'+name,'interaction','learning','learner-A',(ref.identity,),('reason','validate'),100000))
        self.security.install_data(DataUseGrant('X5-validate-'+name,'interaction','learning','learner-A',(kind,),('validate',),(self.endpoint,),'run','internal',100000))

    def context(self, name, refs):
        self.allow_reads()
        return self.runtime.assemble(self.tokens['interaction'],self.protocols[name].ref,'learner-A','learner-A','learning',
            tuple(ContextInput(r,Role.CANONICAL if r.space==Space.CANONICAL else Role.FACTUAL if r.space==Space.FACT else Role.EPISTEMIC) for r in refs),self.versions[name])

    def cognition(self, name, refs, identity, adapter, turn=None):
        self.h.clock.advance()
        ctx = self.context(name,refs)
        self.last_context=ctx
        if turn:self.sessions.bind_context(turn,ctx)
        protocol=self.protocols[name]
        self.security.install_authority(AuthorityGrant('X5-commit-'+identity,'interaction','learning','learner-A',(identity,),('commit',),100000,
            tuple((k,(parameter(k,v)[1],)) for k,v in {'owner':'Interaction','kind':protocol.candidate_kind}.items())))
        candidate=self.runtime.generate_with_llm(self.tokens['interaction'],ctx,adapter,identity=identity)
        review=self.runtime.validate_with_llm(self.tokens['interaction'],candidate,adapter)
        outcome=self.runtime.commit(self.tokens['interaction'],candidate,review.identity)
        self.e.emit('X5_cognition',stage=identity,context=json_value(ctx),candidate=json_value(candidate),review=json_value(review),outcome=json_value(outcome))
        if turn:self.sessions.policy_result(turn,candidate,outcome)
        self.stages.append({'stage':identity,'semantic_status':review.status,'commit_status':outcome.status,'reason':outcome.reason})
        if outcome.status!='Committed':raise PathIncomplete(identity+':'+outcome.status+':'+outcome.reason)
        return candidate.record.ref

    def input(self, identity, text):
        ref=seed(self.h,Ref(Space.FACT,identity,'1'),kind='CurrentInteractionInput',occurrence_key=identity,
            payload={'episode':self.h.get(self.activity).payload['episode'],'text':text,'conversation':'X5'})
        self.sessions.enqueue('X5',ref)
        return ref

    def queue_teaching(self):
        self.teaching_input=self.input('X5-teaching-request','请完整讲解这道题，我想先学习做法')
        try:self.sessions.start('X5')
        except ContractError as exc:self.e.check('queued input cannot start while first turn active',str(exc),'ConversationTurnActive')
        else:self.e.check('queued input cannot start while first turn active',False,True)
        self.e.check('queued request absent from initial frozen Observation context',self.teaching_input not in {i.record.ref for i in self.last_context.items},True)
        self.e.emit('X5_queue_in_flight',input_ref=json_value(self.teaching_input),context_digest=digest(self.last_context))

    def register_action(self, identity, payload, *, transition=None, disclosure='FULL_SOLUTION'):
        body={'exact_payload':payload,'executor_target':'activity-control' if transition else 'mock-display','disclosure_kind':'CONTROL' if transition else disclosure}
        if transition:
            to,episode,task=transition
            body['activity_transition']={'from_ref':json_value(self.activity),'from':self.h.get(self.activity).payload['activity_purpose'],
                'to':to,'episode':episode,'task_ref':json_value(task)}
        ref=seed(self.h,Ref(Space.CANONICAL,identity,'x5-v1'),kind='ActionSemantic',payload=body)
        self.security.install_authority(AuthorityGrant('X5-effect-'+identity,'interaction','learning','learner-A',(identity,),('execute',),100000,
            tuple((k,(parameter(k,v)[1],)) for k,v in {'exact_payload':payload,'executor_target':body['executor_target'],'action_semantic_ref':json_value(ref)}.items())))
        return ref

    def policy(self, label, turn, input_ref, observation, adapter, action=None):
        state=self.h.get(self.activity).payload
        constraint=seed(self.h,Ref(Space.CANONICAL,'X5-envelope-'+label,'v1'),kind='ActivityConstraints',payload={
            'episode':state['episode'],'activity_purpose':state['activity_purpose'],'activity_ref':json_value(self.activity),
            'allowed_action_refs':[json_value(action)] if action else [],
            'reason':'Only this envelope can authorize action selection. Target remains unchanged; a request is not an occurred transition.'})
        refs=(input_ref,observation,self.activity,constraint,self.target,exact_ref(state['task_ref']))+((action,) if action else ())
        policy=self.cognition('policy',refs,'X5-P-'+label,adapter,turn)
        payload=self.h.get(policy).payload
        if not action:
            self.e.check(label+': no teaching action selected',payload['outcome'] in ('NoIntervention','Defer'),True)
            return None
        if payload['outcome']!='Execute':
            raise PathIncomplete(label+':RealPolicyDidNotSelectAction')
        self.e.check(label+': exact authorized action',payload['action_identity'],action.identity)
        self.allow_reads()
        intent=self.actions.create_intent(self.tokens['interaction'],policy,expires_at=self.h.clock.now+1000,idempotency_key='X5-'+label)
        self.sessions.bind_intent(turn,intent)
        self.current_turn,self.current_intent=turn,intent
        if label in ('switch-teaching','explain'):
            # No recorder or prior snapshots are recursively copied into a branch.
            self.pending_snapshots[label]=deepcopy(self,{id(self.e):None,id(self.pending_snapshots):{}})
            self.e.capture(self.h,'before-effect:'+label)
        return intent

    def effect(self, turn, intent, mode='OCCUR_FULL', partial=None):
        control=self.h.get(intent).payload['executor_target']=='activity-control'
        result=(self.control.execute(self.tokens['interaction'],intent,mode=mode) if control else
                self.actions.execute(self.tokens['interaction'],intent,mode=mode,partial_characters=partial))
        self.sessions.effect_result(turn,result)
        payload=self.h.get(result).payload
        if control and payload['status']=='Occurred':self.activity=exact_ref(payload['occurrence_ref'])
        self.e.emit('X5_effect',intent=json_value(self.h.get(intent)),result=json_value(self.h.get(result)),activity_ref=json_value(self.activity))
        return payload

    def run_path(self, adapter):
        first=self.input('X5-initial-input',self.h.get(self.work).payload['text'])
        t1=self.sessions.start('X5')
        before=self.cognition('initial',(self.work,),'X5-O-before',adapter)
        self.pre_evidence=self.commit_scripted('Evidence','X5-E-pre-C2',{
            'description':'The pre-help work chose the unit-rate route; the arithmetic error is separate. This is a scripted local C2 interpretation, not independent overall mastery.',
            'claim_ref':json_value(self.claims['C2']),'independence':'BEFORE_ANY_HELP','impact':'LOCAL_STRATEGY_BASIS'},(before,self.claims['C2']))
        self.policy('initial',t1,first,before,adapter)
        self.sessions.settle(t1)
        t2=self.sessions.start('X5')
        self.e.check('queued teaching input is processed next',self.sessions.turns[t2]['input']==self.teaching_input,True)
        request=self.cognition('request',(self.teaching_input,),'X5-O-teaching-request',adapter)
        switch=self.register_action('SwitchToTeaching','SetActivityPurpose:Teaching',transition=('Teaching',self.episode,self.tasks[0]))
        intent=self.policy('switch-teaching',t2,self.teaching_input,request,adapter,switch)
        self.e.check('intent alone keeps IndependentDiagnosis',self.h.get(self.activity).payload['activity_purpose'],'IndependentDiagnosis')
        self.effect(t2,intent)
        self.sessions.continue_cycle(t2)
        self.e.check('actual control admits Teaching',self.h.get(self.activity).payload['activity_purpose'],'Teaching')
        self.e.check('old activity is historically retained',self.h.get(self.initial_activity).payload['activity_purpose'],'IndependentDiagnosis')
        explanation=self.register_action('RevealFullSolution',EXPLANATION)
        self.e.emit('exact_arithmetic_certificate',given_cost=42,given_kg=6,wanted_kg=15,unit_price=str(Fraction(42,6)),total=str(Fraction(42,6)*15),payload=EXPLANATION)
        self.e.check('registered solution exact arithmetic',[str(Fraction(42,6)),str(Fraction(42,6)*15)],['7','105'])
        intent=self.policy('explain',t2,self.teaching_input,request,adapter,explanation)
        result=self.effect(t2,intent)
        self.explanation_occurrence=exact_ref(result['occurrence_ref'])
        self.sessions.settle(t2)
        new_request=self.input('X5-new-request','我想独立做一道同类题')
        t3=self.sessions.start('X5')
        new_observation=self.cognition('request',(new_request,),'X5-O-new-request',adapter)
        switch=self.register_action('SwitchToIndependentPractice','SetActivityPurpose:IndependentPractice;Task:T-Apple-10-60-7',
            transition=('IndependentPractice','new-apple-episode',self.tasks[1]))
        intent=self.policy('switch-practice',t3,new_request,new_observation,adapter,switch)
        self.effect(t3,intent);self.sessions.continue_cycle(t3)
        question=self.register_action('PresentNewTask',self.h.get(self.tasks[1]).payload['question'],disclosure='TASK_PRESENTATION')
        intent=self.policy('present-task',t3,new_request,new_observation,adapter,question)
        self.effect(t3,intent);self.sessions.settle(t3)
        self.episode='new-apple-episode'
        work=seed(self.h,Ref(Space.FACT,'X5-new-work','1'),kind='LearnerWorkSubmitted',occurrence_key='X5-new-work',payload={
            'episode':self.episode,'task':self.h.get(self.tasks[1]).payload['question'],'text':'60 / 10 = 6; 6 * 7 = 42; Answer = 42'})
        final_input=self.input('X5-final-input',self.h.get(work).payload['text'])
        t4=self.sessions.start('X5')
        observation=self.cognition('new-work',(work,),'X5-O-new-work',adapter)
        evidence=self.commit_scripted('Evidence','X5-E-new-C1',{
            'description':'Correct performance on the distinct new task after a recent full explanation in the same task family. No solution was supplied on this new task. Recent teaching remains material: this does not establish independent mastery and does not count the repeated strategy as new independent strategy selection. Preserve the separate pre-help C2 basis.',
            'claim_ref':json_value(self.claims['C1']),'independence':'RECENT_TEACHING_NOT_INDEPENDENT_MASTERY',
            'impact':'LOCAL_NEW_TASK_SUCCESS_WITH_RECENT_TEACHING'},
            (observation,work,self.tasks[1],self.explanation_occurrence,self.pre_evidence,self.claims['C1']))
        belief=self.commit_scripted('LearnerBelief','X5-Belief',{'description':'Scripted Evaluation: retain pre-help local strategy evidence and recent-teaching-conditioned new-task success; independent mastery remains unestablished.'},(evidence,))
        self.policy('final',t4,final_input,observation,adapter);self.sessions.settle(t4)
        view=self.exposure(work)
        self.e.check('new task presentation is not solution assistance',view['exposures'],[])
        self.e.check('new Evidence retains recent old-task actual explanation',self.explanation_occurrence in {d.target for d in self.h.get(evidence).dependencies},True)
        self.e.check('pre-help C2 basis precedes actual explanation',self.h.get(self.pre_evidence).recorded_at < self.h.get(self.explanation_occurrence).recorded_at,True)
        self.e.check('Target unchanged',self.h.get(self.target)==self.initial_target,True)
        self.e.check('initial work unchanged',self.h.get(self.work)==self.initial_fact,True)
        self.e.check('all four turns settled',not self.sessions.active and not self.sessions.queues['X5'] and len(self.sessions.turns)==4,True)
        self.e.emit('X5_final_lineage',evidence=json_value(self.h.get(evidence)),belief=json_value(self.h.get(belief)),recent_explanation=json_value(self.h.get(self.explanation_occurrence)))
        return {'coverage':'COMPLETE','result':'PASS'}


def run_boundary(w, e, variant):
    w=deepcopy(w,{id(w.pending_snapshots):{}});w.e=e
    e.capture(w.h,'boundary_initial')
    old=w.activity
    mode={'control-not-occurred':'NOT_OCCURRED','explanation-not-occurred':'NOT_OCCURRED',
          'explanation-partial':'OCCUR_PARTIAL','explanation-indeterminate':'INDETERMINATE'}[variant]
    result=w.effect(w.current_turn,w.current_intent,mode,32 if mode=='OCCUR_PARTIAL' else None)
    expected={'NOT_OCCURRED':'NotOccurred','OCCUR_PARTIAL':'Occurred','INDETERMINATE':'Indeterminate'}[mode]
    e.check('boundary terminal status',result['status'],expected)
    if variant=='control-not-occurred':
        e.check('failed Control retains exact previous activity',json_value(w.activity),json_value(old))
        e.check('failed Control cannot authorize Teaching',w.h.get(w.activity).payload['activity_purpose'],'IndependentDiagnosis')
        try:w.sessions.continue_cycle(w.current_turn)
        except ContractError as exc:e.check('no continuation after failed Control',str(exc),'SuccessfulControlRequired')
        else:e.check('no continuation after failed Control',False,True)
        e.check('no disclosure caused by failed Control',sum(r.kind=='ActionOccurrence' for r in w.h.facts.records()),0)
        policy=w.h.get(exact_ref(w.h.get(w.current_intent).payload['policy_ref']))
        injected={**policy.payload,'action_identity':'RevealFullSolution','action_revision':'x5-v1',
                  'exact_payload':EXPLANATION,'executor_target':'mock-display'}
        candidate=w.runtime.propose(w.last_context,policy.ref.identity,'r2',injected,expected_head=policy.ref)
        review=w.runtime.record_semantic_validation(w.tokens['interaction'],candidate,'PASS',
            'Deliberately scripted PASS for negative gate isolation; not a real model result.','X5-NEGATIVE-FIXTURE',fixture=True)
        outcome=w.runtime.commit(w.tokens['interaction'],candidate,review.identity)
        e.emit('negative_gate_fixture',candidate=json_value(candidate),review=json_value(review),outcome=json_value(outcome))
        e.check('failed switch cannot commit full solution even with fixture PASS',outcome.reason,'ActionOutsideActivityEnvelope')
        e.check('forbidden candidate has no formal standing',w.h.get(candidate.record.ref) is None,True)
    else:
        response=w.response('boundary-'+variant)
        view=w.exposure(response)
        e.check('planned full explanation never admitted as actual',any(x['payload']==EXPLANATION for x in view['exposures']),False)
        if mode=='OCCUR_PARTIAL':
            e.check('only actual partial display retained',[(x['payload'],x['completeness']) for x in view['exposures']],[(EXPLANATION[:32],'PARTIAL')])
        else:
            e.check('unacknowledged explanation has no occurrence',view['exposures'],[])
            e.check('absence and uncertainty remain distinct',[x['status'] for x in view['unconfirmed']],[expected])
        e.check('learner use is never inferred',view['learner_used_assistance'],'NOT_INFERRED')
    w.sessions.settle(w.current_turn)
    w.allow_reads()
    again=(w.control if variant=='control-not-occurred' else w.actions).execute(w.tokens['interaction'],w.current_intent)
    e.check('terminal effect cannot be retried into success',w.h.get(again).payload,result)
    e.check('Target unchanged at boundary',w.h.get(w.target)==w.initial_target,True)
    e.capture(w.h,'boundary_final')
    return {'variant':variant,'coverage':'COMPLETE','result':'PASS' if all(c['passed'] for c in e.checks) else 'FAIL',
            'checks':len(e.checks),'model_calls':0,'failed_checks':[c for c in e.checks if not c['passed']]}
