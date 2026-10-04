"""X1/X2 compose exact versions, owner correction, real Policy and serial effects."""
from copy import deepcopy
from dataclasses import replace

from .boundary import ContextInput, Protocol, digest
from .cases import seed
from .policy_cases import PolicyWorld
from .records import Record, Ref, Role, Space, json_value
from .runtime import Activation, Compatibility, ContractError, Decision
from .security import AuthorityGrant
from .session import SerialSession


class CompositionWorld(PolicyWorld):
    def __init__(self, e, definition, fixture):
        super().__init__(e, definition, fixture, fixture['variants'][1])
        self.x_protocols = {}
        for revision in ('v1', 'v2'):
            ref = seed(self.h, Ref(Space.CANONICAL, 'XPolicyProtocol', revision), kind='ReasoningProtocol',
                payload={**definition, 'identity':'XPolicyProtocol', 'version':revision,
                         'composition_scope':'Compatible version fixture; unchanged E1 prompts and rules.'})
            p = Protocol(ref, 'PolicyOutcome', 'Interaction', self.protocol.allowed_context_kinds + ('ActionOccurrence',),
                         self.protocol.fields, self.protocol.semantic_rule, self.endpoint)
            self.x_protocols[revision] = p
            self.runtime.register_protocol(p)
            self.h.canonical.add_compatibility_fixture(Compatibility('X-compatible-' + revision,
                (ref, p.semantic_rule), 'learner-A', 'learning', Decision.ALLOW))
        self.security.install_authority(AuthorityGrant('X-reason', 'interaction', 'learning', 'learner-A',
            ('XPolicyProtocol',), ('reason','validate'), 100000))
        self.security.install_authority(AuthorityGrant('X-P2-commit', 'interaction', 'learning', 'learner-A',
            ('P2',), ('commit',), 100000, self.security._authority['E1-commit'].parameter_constraints))
        self.h.canonical.activate_fixture(Activation('X-initial-v1', self.x_protocols['v1'].ref,
            'learner-A','learning',self.h.clock.advance()))
        self.h.canonical.activate_fixture(Activation('X-initial-rule', self.protocol.semantic_rule,
            'learner-A','learning',self.h.clock.advance()))
        self.base_inputs = tuple(i.record.ref for i in self.context.items
                                if i.record.ref not in (self.input,self.before_observation))
        self.current_observation = self.before_observation
        self.sessions = SerialSession(self.runtime)
        self.sessions.enqueue('C', self.input)
        self.turn = self.sessions.start('C')
        self.context = self.make_context(self.turn, self.input)
        self.sessions.bind_context(self.turn, self.context)
        self.e.emit('X_initial', context=json_value(self.context), turn_ref=json_value(self.turn),
                    old_observation=json_value(self.before_observation))

    def branch(self, e): return deepcopy(self, {id(self.e):e})

    def make_context(self, turn, input_ref, extra=()):
        self.sessions.require(turn, 'INPUT')
        self.allow_reads()
        active = self.h.canonical.active('XPolicyProtocol','learner-A','learning',self.h.clock.now).target
        p = self.runtime._protocols[active]
        versions = self.h.canonical.bind_active((active.identity,p.semantic_rule.identity),
            'learner-A','learning',self.h.clock.now,'X-compatible-'+active.revision)
        refs = (*self.base_inputs,self.current_observation,input_ref,*extra)
        return self.runtime.assemble(self.tokens['interaction'], active, 'learner-A','learner-A','learning',
            tuple(ContextInput(r,Role.CANONICAL if r.space == Space.CANONICAL else
                               Role.FACTUAL if r.space == Space.FACT else Role.EPISTEMIC) for r in refs),versions)

    def queue_next(self):
        self.second_input = seed(self.h, Ref(Space.FACT,'X-next-input','1'), kind='CurrentInteractionInput',
            payload={'conversation':'C','episode':self.episode,'text':'请再给我一点局部提示，让我继续自己算。'})
        self.sessions.enqueue('C',self.second_input)
        self.blocked('generation in flight')
        self.e.check('queued input absent from original Context',
            self.second_input not in {i.record.ref for i in self.context.items},True)

    def blocked(self, label):
        try:
            self.sessions.start('C')
        except ContractError as exc:
            self.e.check(label+': no same-conversation overlap',str(exc),'ConversationTurnActive')
        else: self.e.check(label+': no same-conversation overlap',False,True)

    def external_correction(self):
        source = seed(self.h,Ref(Space.FACT,'X-correction-owner','1'),kind='ExternalOwnerInput',
            payload={'owner':'Interaction','conversation':'C-external','meaning':'SCRIPTED-OWNER-REINTERPRETATION'})
        correction = seed(self.h,Ref(Space.FACT,'X-observation-correction','1'),kind='CorrectionOccurred',
            corrects=self.before_observation,payload={'source':json_value(source),'owner':'Interaction',
            'reason':'Trusted fixture withdraws the old annotation before committing its more precise replacement.'})
        self.allow_reads()
        p = self.protocols['Observation']
        context = self.runtime.assemble(self.tokens['interaction'],p.ref,'learner-A','learner-A','learning',
            (ContextInput(self.work,Role.FACTUAL),),self.versions['Observation'])
        c = self.runtime.propose(context,self.before_observation.identity,'r2',
            {'description':'The written quotient 42 / 6 = 8 is incorrect (it is 7). The later multiplication 8 * 15 = 120 is consistent with the written quotient; the task result should be 105.'},
            expected_head=self.before_observation)
        c = replace(c,record=replace(c.record,provenance=c.record.provenance+('external-owner-input:'+source.identity,)))
        self.runtime._candidates[c.identity] = c
        review = self.runtime.record_semantic_validation(self.tokens['interaction'],c,'PASS',
            'Predeclared independent owner fixture, not a queued learner input interpretation.','SCRIPTED-X-OWNER',fixture=True)
        outcome = self.runtime.commit(self.tokens['interaction'],c,review.identity)
        self.e.emit('X_owner_correction',source=json_value(self.h.get(source)),correction=json_value(self.h.get(correction)),
            candidate=json_value(c),review=json_value(review),outcome=json_value(outcome))
        self.e.check('independent owner replacement commits during active turn',outcome.status,'Committed')
        self.e.check('original turn remains active during owner update',self.sessions.active['C']==self.turn,True)
        self.current_observation = c.record.ref

    def activate_v2(self):
        source = seed(self.h,Ref(Space.FACT,'X-governance-activation','1'),kind='GovernanceInput',
            payload={'owner':'Evolution','conversation':'C-governance','source':'TRUSTED-GOVERNANCE-FIXTURE'})
        a = Activation('X-activate-v2',self.x_protocols['v2'].ref,'learner-A','learning',self.h.clock.advance())
        self.h.canonical.activate_fixture(a)
        self.e.emit('X_activation',source=json_value(self.h.get(source)),activation=json_value(a))
        self.e.check('future boundary resolves v2',self.h.canonical.active('XPolicyProtocol','learner-A','learning',self.h.clock.now).target.revision,'v2')

    def revoke_v1(self):
        source = seed(self.h,Ref(Space.FACT,'X-governance-revocation','1'),kind='GovernanceInput',
            payload={'owner':'Evolution','source':'TRUSTED-GOVERNANCE-FIXTURE','reason':'Explicit withdrawal of v1 eligibility for learning.'})
        record = Record.create(ref=Ref(Space.FACT,'X-v1-revoked','1'),kind='VersionRevocationOccurred',
            subject='learner-A',owner='Evolution',recorded_at=self.h.clock.advance(),
            payload={'target':json_value(self.x_protocols['v1'].ref),'source':json_value(source)},
            provenance=('trusted-governance-fixture',source.identity))
        self.h.seed_committed_fixture(record)
        self.e.emit('X_revocation',record=json_value(record))

    def reason(self,adapter,turn,context,identity):
        self.sessions.require(turn,'POLICY')
        c = self.runtime.generate_with_llm(self.tokens['interaction'],context,adapter,identity=identity)
        review = self.runtime.validate_with_llm(self.tokens['interaction'],c,adapter)
        self.e.emit('X_policy',turn_ref=json_value(turn),context=json_value(context),candidate=json_value(c),review=json_value(review))
        return c,review

    def commit_policy(self,turn,c,review):
        outcome = self.runtime.commit(self.tokens['interaction'],c,review.identity)
        self.sessions.policy_result(turn,c,outcome)
        self.e.emit('X_commit',turn_ref=json_value(turn),candidate_digest=digest(c),outcome=json_value(outcome))
        return outcome

    def effect(self,turn,c,*,revoke=False):
        self.allow_reads()
        intent = self.actions.create_intent(self.tokens['interaction'],c.record.ref,
            expires_at=self.h.clock.now+1000,idempotency_key='X-effect-'+c.record.ref.identity)
        self.sessions.bind_intent(turn,intent)
        if revoke: self.revoke_v1()
        result = self.actions.execute(self.tokens['interaction'],intent)
        record = self.h.get(result)
        self.e.emit('X_effect',intent=json_value(self.h.get(intent)),result=json_value(record))
        self.sessions.effect_result(turn,result)
        return record.payload

    def next_decision(self,adapter):
        self.blocked('before original turn settles')
        self.sessions.settle(self.turn)
        turn = self.sessions.start('C')
        extras = tuple(r.ref for r in self.h.facts.records() if r.kind == 'ActionOccurrence')
        context = self.make_context(turn,self.second_input,extras)
        self.sessions.bind_context(turn,context)
        self.e.emit('X_future_context',context=json_value(context),turn_ref=json_value(turn))
        self.e.check('new Context contains current exact Observation',
            self.current_observation in {i.record.ref for i in context.items},True)
        c,review = self.reason(adapter,turn,context,'P2')
        outcome = self.commit_policy(turn,c,review)
        if review.status != 'PASS':
            return {'coverage':'INCOMPLETE','reason':'FutureSemanticReview:'+review.status}
        self.e.check('future Policy commits',outcome.status,'Committed')
        if outcome.status != 'Committed': return {'coverage':'INCOMPLETE','reason':'FuturePolicyNotCommitted'}
        if c.record.payload['outcome'] == 'Execute':
            result = self.effect(turn,c)
            self.e.check('future selected effect occurs',result['status'],'Occurred')
        self.sessions.settle(turn)
        self.e.check('both turns settled',not self.sessions.active and not self.sessions.queues['C'],True)
        return {'coverage':'COMPLETE','future_protocol':json_value(context.protocol),'future_commit':outcome.status}


def run_composition(w,branch,adapter,injection):
    frozen = digest(w.context)
    old_protocol = w.h.get(w.x_protocols['v1'].ref)
    c,review = w.reason(adapter,w.turn,w.context,'P')
    w.e.check('in-flight stimulus occurred once',injection['calls'],1)
    w.e.check('original Context not silently rebased',digest(w.context),frozen)
    w.e.check('original model candidate retains v1',c.protocol.revision,'v1')
    outcome = w.commit_policy(w.turn,c,review)
    result = {'commit_status':outcome.status,'commit_reason':outcome.reason,'outcome':c.record.payload['outcome']}
    if review.status != 'PASS': return {**result,'coverage':'INCOMPLETE','reason':'SemanticReview:'+review.status}
    if branch == 'X1-correction':
        w.e.check('corrected exact basis rejects original candidate',outcome.status,'CandidateStale')
        w.e.check('rejection caused by correction',outcome.reason,'Corrected')
        w.e.check('old candidate has no formal standing',w.h.get(c.record.ref) is None,True)
        w.e.check('no T1 intent after correction',any(r.kind=='ActionIntent' for r in w.h.executions.records()),False)
        if outcome.status != 'CandidateStale': return {**result,'coverage':'INCOMPLETE'}
        future = w.next_decision(adapter)
        return {**result,**future}
    w.e.check('activation alone does not stale v1 candidate',outcome.status,'Committed')
    if outcome.status != 'Committed': return {**result,'coverage':'INCOMPLETE'}
    if c.record.payload['outcome'] != 'Execute':
        w.sessions.settle(w.turn)
        return {**result,'coverage':'INCOMPLETE','reason':'RealPolicyDidNotSelectAction'}
    effect = w.effect(w.turn,c,revoke=branch=='X2-revoke')
    result['effect_status'] = effect['status']
    w.e.check('exact v1 canonical record remains immutable',w.h.get(old_protocol.ref)==old_protocol,True)
    if branch == 'X2-revoke':
        w.e.check('revoked version prevents display',effect['status'],'NotOccurred')
        w.e.check('effect fails for version eligibility',effect['reason'],'EffectPrecondition:VersionIneligible')
        w.e.check('no display acknowledgement or occurrence after revocation',
            any(r.kind in ('DisplayAcknowledgement','ActionOccurrence') for history in (w.h.executions,w.h.facts) for r in history.records()),False)
        w.sessions.settle(w.turn)
        return {**result,'coverage':'COMPLETE'}
    w.e.check('superseded but eligible v1 effect occurs',effect['status'],'Occurred')
    future = w.next_decision(adapter)
    if future['coverage'] == 'COMPLETE': w.e.check('future decision binds v2',future['future_protocol']['revision'],'v2')
    return {**result,**future}
