"""E2 controlled interleavings with real Policy calls and shared formal state."""
from copy import deepcopy
from dataclasses import replace

from .boundary import ContextInput, Protocol, digest
from .cases import seed
from .policy_cases import PolicyWorld
from .records import Ref, Role, Space, VersionContext, json_value
from .runtime import Compatibility, ContractError, Decision
from .security import AuthorityGrant
from .session import SerialSession


class SerialWorld(PolicyWorld):
    def __init__(self, evidence, definition, policy_fixture):
        super().__init__(evidence, definition, policy_fixture, policy_fixture['variants'][1])
        self.evidence_basis = self.commit_scripted('Evidence', 'E2-E', {
            'description': 'Scripted shared basis for the local task; no stable ability inference.',
            'claim_ref': json_value(Ref(Space.CANONICAL,'C1','v1')),
            'independence': 'LOCAL_EPISODE', 'impact': 'SCRIPTED-FOR-CONCURRENCY'},
            (self.before_observation, Ref(Space.CANONICAL,'C1','v1')))
        self.belief = self.commit_scripted('LearnerBelief', 'E2-Belief',
            {'description': 'Shared fixture state r1: this local error may be considered by Policy; it does not establish stable ability.'}, (self.evidence_basis,))
        ref = seed(self.h, Ref(Space.CANONICAL,'E2PolicyProtocol','v1'), kind='ReasoningProtocol',
            payload={**definition, 'identity':'E2PolicyProtocol', 'extension':'CURRENT shared Belief with explicit require_head; unchanged E1 Policy prompts.'})
        self.e2_protocol = Protocol(ref,'PolicyOutcome','Interaction',self.protocol.allowed_context_kinds+('LearnerBelief','ActionOccurrence'),
            self.protocol.fields,self.protocol.semantic_rule,self.endpoint)
        self.runtime.register_protocol(self.e2_protocol)
        self.h.canonical.add_compatibility_fixture(Compatibility('E2-compatible',(ref,self.protocol.semantic_rule),
            'learner-A','learning',Decision.ALLOW))
        self.security.install_authority(AuthorityGrant('E2-reason','interaction','learning','learner-A',
            (ref.identity,),('reason','validate'),100000))
        self.add_protocol('Observation','Interaction',('CurrentInteractionInput',),(('description','string'),))
        self.base_inputs = tuple(i.record.ref for i in self.context.items if i.record.ref != self.input)
        self.sessions = SerialSession(self.runtime)
        self.sessions.enqueue('C',self.input)
        self.turn = self.sessions.start('C')
        self.context = self.make_context(self.turn,self.input)
        self.sessions.bind_context(self.turn,self.context)
        self.e.emit('E2_initial', context=json_value(self.context), turn_ref=json_value(self.turn),
            shared_belief=json_value(self.belief), belief_semantics='SCRIPTED-EVALUATION-FIXTURE')

    def branch(self,evidence):
        return deepcopy(self,{id(self.e):evidence})

    def make_context(self,turn,input_ref,extra=()):
        self.sessions.require(turn,'INPUT')
        self.allow_reads()
        requests = tuple(ContextInput(ref,Role.CANONICAL if ref.space==Space.CANONICAL else Role.FACTUAL if ref.space==Space.FACT else Role.EPISTEMIC)
            for ref in (*self.base_inputs,input_ref,*extra))+(ContextInput(self.belief,Role.EPISTEMIC,require_head=True),)
        return self.runtime.assemble(self.tokens['interaction'],self.e2_protocol.ref,'learner-A','learner-A','learning',requests,
            VersionContext((self.e2_protocol.ref,self.e2_protocol.semantic_rule),compatibility_basis='E2-compatible'))

    def queue_second(self):
        self.second_input=seed(self.h,Ref(Space.FACT,'E2-input-T2','1'),kind='CurrentInteractionInput',
            occurrence_key='E2-input-T2',payload={'conversation':'C','episode':self.episode,'text':'先别提示，让我自己再算一次'})
        self.sessions.enqueue('C',self.second_input)
        self.e.emit('T2_received',fact=json_value(self.h.get(self.second_input)))
        self.assert_blocked('during Policy reasoning')
        self.e.check('T2 absent from frozen T1 context',self.second_input not in {i.record.ref for i in self.context.items},True)

    def assert_blocked(self,label):
        try:
            self.sessions.start('C')
        except ContractError as exc:
            self.e.check(label+': same conversation cannot start next turn',str(exc),'ConversationTurnActive')
        else:
            self.e.check(label+': same conversation cannot start next turn',False,True)
        self.e.check(label+': no T2 Observation or Policy generation',
            any(r.kind=='CandidateGeneration' and self.h.get(r.ref).payload.get('context_id') in {
                c.identity for c in self.runtime._contexts.values() if any(i.record.ref==self.second_input for i in c.items)}
                for r in self.h.executions.records()),False)

    def external_update(self):
        source=seed(self.h,Ref(Space.FACT,'E2-external-owner','1'),kind='ExternalOwnerInput',
            payload={'conversation':'C-external','owner':'Evaluation','source':'PREDECLARED-INDEPENDENT-OWNER-UPDATE'})
        protocol=self.protocols['LearnerBelief'];token=self.tokens['evaluation']
        self.allow_reads()
        context=self.runtime.assemble(token,protocol.ref,'learner-A','learner-A','learning',
            (ContextInput(self.evidence_basis,Role.EPISTEMIC),),self.versions['LearnerBelief'])
        candidate=self.runtime.propose(context,self.belief.identity,'r2',
            {'description':'Shared fixture state r2: independent Evaluation owner has revised the current basis; the old decision must not silently rebase.'},expected_head=self.belief)
        candidate=replace(candidate,record=replace(candidate.record,provenance=candidate.record.provenance+('external-owner-input:'+source.identity,)))
        self.runtime._candidates[candidate.identity]=candidate
        review=self.runtime.record_semantic_validation(token,candidate,'PASS','Declared external owner fixture, not a queued input interpretation.',
            'SCRIPTED-EXTERNAL-OWNER',fixture=True)
        outcome=self.runtime.commit(token,candidate,review.identity)
        self.e.emit('external_owner_commit',source=json_value(self.h.get(source)),candidate=json_value(candidate),review=json_value(review),outcome=json_value(outcome))
        self.e.check('external owner can commit while C is active',outcome.status,'Committed')
        self.e.check('no learner-wide lock',self.sessions.active.get('C')==self.turn,True)
        self.e.check('exact r1 remains in frozen decision',any(i.record.ref==self.belief for i in self.context.items),True)
        return candidate.record.ref

    def generate_and_validate(self,adapter,turn,context,identity='P'):
        self.sessions.require(turn,'POLICY')
        candidate=self.runtime.generate_with_llm(self.tokens['interaction'],context,adapter,identity=identity)
        review=self.runtime.validate_with_llm(self.tokens['interaction'],candidate,adapter)
        self.e.emit('serial_candidate',turn_ref=json_value(turn),candidate=json_value(candidate),review=json_value(review))
        return candidate,review

    def commit_and_record(self,turn,candidate,review):
        outcome=self.runtime.commit(self.tokens['interaction'],candidate,review.identity)
        self.sessions.policy_result(turn,candidate,outcome)
        self.e.emit('serial_commit',turn_ref=json_value(turn),outcome=json_value(outcome))
        return outcome


def run_branch(w,branch,adapter,injection):
    """injection is invoked by the transport after generation starts, before it returns."""
    before=digest(w.context)
    candidate,review=w.generate_and_validate(adapter,w.turn,w.context)
    w.e.check('in-flight stimulus ran exactly once',injection['calls'],1)
    w.e.check('frozen context unchanged',digest(w.context),before)
    outcome=w.commit_and_record(w.turn,candidate,review)
    if branch=='B-external-before-commit':
        w.e.check('old candidate rejected',outcome.status,'CandidateStale')
        w.e.check('head requirement detects exact old basis',outcome.reason,'RequiredHeadChanged')
        w.e.check('stale candidate has no standing',w.h.get(candidate.record.ref) is None,True)
        w.e.check('no ActionIntent after stale rejection',any(r.kind=='ActionIntent' for r in w.h.executions.records()),False)
        w.sessions.settle(w.turn)
        return {'coverage':'COMPLETE','commit_status':outcome.status,'outcome':candidate.record.payload['outcome']}
    w.e.check('policy commit succeeds with unchanged basis',outcome.status,'Committed')
    if outcome.status!='Committed':
        return {'coverage':'INCOMPLETE','reason':'PolicyNotCommitted'}
    if candidate.record.payload['outcome']!='Execute':
        w.sessions.settle(w.turn)
        return {'coverage':'INCOMPLETE','reason':'RealPolicyDidNotSelectAction'}
    w.allow_reads()
    intent=w.actions.create_intent(w.tokens['interaction'],candidate.record.ref,expires_at=w.h.clock.now+1000,idempotency_key='E2-T1-effect')
    w.sessions.bind_intent(w.turn,intent)
    if branch=='A-queue':
        w.assert_blocked('intent pending effect')
    else:
        w.external_update()
    result_ref=w.actions.execute(w.tokens['interaction'],intent)
    result=w.h.get(result_ref).payload
    w.e.emit('serial_effect',intent=json_value(w.h.get(intent)),result=json_value(w.h.get(result_ref)))
    if branch=='A-queue':
        w.e.check('ordinary queue does not prevent valid effect',result['status'],'Occurred')
        w.assert_blocked('effect returned but result not yet processed')
    else:
        w.e.check('external change before effect blocks display',result['status'],'NotOccurred')
        w.e.check('effect rejects old head',result['reason'],'EffectPrecondition:RequiredHeadChanged')
        w.e.check('no display acknowledgement or occurrence',any(r.kind=='ActionOccurrence' for r in w.h.facts.records()),False)
    w.sessions.effect_result(w.turn,result_ref)
    if branch=='A-queue':w.assert_blocked('result processed but turn not yet settled')
    w.sessions.settle(w.turn)
    if branch=='A-queue':
        t2=w.sessions.start('C')
        # Input interpretation is a declared fixture, invoked only after T1 settles.
        w.e.emit('T2_interpretation_started',turn_ref=json_value(t2),input_ref=json_value(w.second_input))
        observation=w.commit_scripted('Observation','E2-O-T2',
            {'description':'The learner requests no hint for now and wants to recompute independently.'},(w.second_input,))
        occurrence=Ref(Space.FACT,result['occurrence_ref']['identity'],result['occurrence_ref']['revision']) if result['occurrence_ref'] else None
        ctx=w.make_context(t2,w.second_input,(observation,)+( (occurrence,) if occurrence else ()))
        w.sessions.bind_context(t2,ctx)
        w.e.check('T2 context includes its input only after T1 settles',w.second_input in {i.record.ref for i in ctx.items},True)
        w.security.install_authority(AuthorityGrant('E2-P2-commit','interaction','learning','learner-A',('P2',),('commit',),100000,
            w.security._authority['E1-commit'].parameter_constraints))
        c2,r2=w.generate_and_validate(adapter,t2,ctx,'P2')
        o2=w.commit_and_record(t2,c2,r2)
        w.e.check('T2 commits after T1 result processing',o2.status,'Committed')
        if o2.status=='Committed' and c2.record.payload['outcome']=='Execute':
            w.allow_reads()
            i2=w.actions.create_intent(w.tokens['interaction'],c2.record.ref,expires_at=w.h.clock.now+1000,idempotency_key='E2-T2-effect')
            w.sessions.bind_intent(t2,i2)
            er2=w.actions.execute(w.tokens['interaction'],i2)
            w.sessions.effect_result(t2,er2)
        w.sessions.settle(t2)
        w.e.check('both ordinary turns settle with empty queue',not w.sessions.active and not w.sessions.queues['C'],True)
    return {'coverage':'COMPLETE','commit_status':outcome.status,'effect_status':result['status'],'outcome':candidate.record.payload['outcome']}
