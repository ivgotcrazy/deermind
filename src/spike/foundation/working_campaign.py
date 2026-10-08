"""Pinned working configuration on shared runtime; caller supplies transport."""
import json
import time
from dataclasses import replace
from pathlib import Path

from .actions import exact_ref
from .boundary import ContextInput, Protocol, digest
from .cases import seed
from .llm import ModelFailure
from .policy_cases import PolicyWorld
from .records import Ref, Role, Space, VersionContext, json_value
from .runtime import Compatibility, ContractError, Decision
from .security import AuthorityGrant, DataUseGrant, AccessDenied, parameter
from .working_entry import RestrictedEntry, WorkingScope

ROOT = Path(__file__).resolve().parents[3]


class CallBudget:
    def __init__(self, adapter, budget, clock=time.monotonic):
        self.adapter, self.budget, self.clock = adapter, budget, clock
        self.deadline = clock() + budget['wall_time_seconds']
        self.initial = adapter.calls
        self.case_initial, self.case_limit = adapter.calls, 0

    @property
    def config(self): return self.adapter.config

    @property
    def records(self): return self.adapter.records

    def begin_case(self, limit):
        self.case_initial, self.case_limit = self.adapter.calls, limit

    def complete(self, messages, purpose, *, output_contract=None):
        remaining = self.deadline - self.clock()
        if remaining <= 0: raise ModelFailure('WorkingDeadlineExhausted')
        if (self.adapter.calls - self.initial >= self.budget['max_calls']
                or self.adapter.calls - self.case_initial >= self.case_limit):
            raise ModelFailure('WorkingCallBudgetExhausted')
        original = self.adapter.config
        self.adapter.config = replace(original, timeout_seconds=min(original.timeout_seconds, remaining))
        try:
            value = self.adapter.complete(messages, purpose, output_contract=output_contract)
        finally:
            self.adapter.config = original
        if self.clock() >= self.deadline: raise ModelFailure('WorkingDeadlineReachedAfterCall')
        return value


class WorkingWorld(PolicyWorld):
    def __init__(self, evidence, config, case, *, fixed_control=False):
        definitions = {b['role']:json.loads((ROOT/b['path']).read_text(encoding='utf-8'))
                       for b in config['protocol_bindings']}
        fixture = {'actions':[{'identity':r['identity'], 'payload':config['action_payloads'][r['identity']],
                               'admissible':True} for r in config['profile']['actions']]}
        super().__init__(evidence, definitions['policy'], fixture, {'text':case['request']}, rule_revision='v4')
        self.config, self.case = config, case
        self.work = seed(self.h, Ref(Space.FACT, 'WorkingSubmittedWork', '1'), kind='LearnerWorkSubmitted',
            occurrence_key='working-submitted-work', payload={'task':config['task']['question'],
                'text':case['work'], 'episode':config['activity']['episode']})
        self.input = seed(self.h, Ref(Space.FACT, 'WorkingReceivedInput', '1'), kind='CurrentInteractionInput',
            occurrence_key='working-received-input', payload={'text':case['request'], 'episode':config['activity']['episode']})
        self.constraints = seed(self.h, exact_ref(config['profile']['constraints']), kind='ActivityConstraints',
            payload={**config['activity'], 'allowed_action_refs':config['profile']['actions']})
        self.working_protocols = {'policy':self.protocol}
        self.working_versions = {'policy':VersionContext(
            (self.protocol.ref, self.protocol.semantic_rule, self.utility_rule), compatibility_basis='E1-compatible-v4')}
        for binding in config['protocol_bindings']:
            if binding['role'] == 'policy': continue
            definition = definitions[binding['role']]
            ref = seed(self.h, exact_ref(binding['protocol_ref']), kind='ReasoningProtocol', payload=definition)
            rule = seed(self.h, exact_ref(binding['semantic_rule_ref']), kind='SemanticValidationRules',
                payload={'system':definition['validation_system'], 'format':definition['validation_format'],
                         'criteria':definition['criteria']})
            kinds = ('LearnerWorkSubmitted',) if binding['role'] == 'work' else ('CurrentInteractionInput',)
            protocol = Protocol(ref, 'Observation', 'Interaction', kinds, (('description','string'),), rule, self.endpoint)
            self.runtime.register_protocol(protocol)
            name = 'working-' + binding['role']
            self.h.canonical.add_compatibility_fixture(Compatibility(name, (ref,rule), 'learner-A','learning',Decision.ALLOW))
            self.working_protocols[binding['role']] = protocol
            self.working_versions[binding['role']] = VersionContext((ref,rule), compatibility_basis=name)
            self.security.install_authority(AuthorityGrant(name,'interaction','learning','learner-A',
                                                         (ref.identity,),('reason','validate'),100000))
        self.security.install_data(DataUseGrant('WorkingObservationValidate','interaction','learning','learner-A',
            ('Observation',),('validate',),(self.endpoint,),'run','internal',100000))
        # Explicit fixed-review source, never substituted for normal generated Observation.
        self.fixed_observation = self.commit_scripted('Observation', 'WorkingFixedReviewBasis',
            {'description':'SCRIPTED FIXED REVIEW BASIS: the submitted unit-rate route has incorrect division and final answer; no ability or teaching decision.'},
            (self.work,)) if fixed_control else None
        self.allow_reads()
        self.entry = RestrictedEntry(self.runtime, WorkingScope(**{
            **config['profile'], 'protocols':tuple(exact_ref(r) for r in config['profile']['protocols']),
            'constraints':exact_ref(config['profile']['constraints']),
            'actions':tuple(exact_ref(r) for r in config['profile']['actions'])}))
        self.sessions = self.entry.session
        self.sessions.enqueue('WorkingConversation', self.input)
        self.turn = self.sessions.start('WorkingConversation')
        for identity, kind in [('WorkingObservation','Observation'),('WorkingPolicy','PolicyOutcome')]:
            constraints = tuple((k,(parameter(k,v)[1],)) for k,v in {'owner':'Interaction','kind':kind}.items())
            self.security.install_authority(AuthorityGrant('WorkingCommit-'+identity,'interaction','learning','learner-A',
                (identity,),('commit',),100000,constraints))

    def observation_context(self, role):
        self.allow_reads()
        ref = self.work if role == 'work' else self.input
        context = self.runtime.assemble(self.tokens['interaction'], self.working_protocols[role].ref,
            'learner-A','learner-A','learning',(ContextInput(ref,Role.FACTUAL),),self.working_versions[role])
        self.sessions.bind_reasoning_context(self.turn, context)
        return context

    def policy_context(self, observation):
        self.allow_reads()
        refs = (self.work, observation, self.input, self.constraints, *self.action_refs)
        context = self.runtime.assemble(self.tokens['interaction'], self.protocol.ref, 'learner-A','learner-A','learning',
            tuple(ContextInput(r,Role.CANONICAL if r.space == Space.CANONICAL else
                               Role.FACTUAL if r.space == Space.FACT else Role.EPISTEMIC) for r in refs),
            self.working_versions['policy'])
        self.sessions.bind_context(self.turn, context)
        return context

    def close_failure(self):
        if self.sessions.turns[self.turn]['phase'] == 'SETTLED': return
        if self.sessions.turns[self.turn]['phase'] != 'CLOSING':
            failure = self.runtime.execution('TurnFailure','learner-A',{'turn_ref':json_value(self.turn),
                                            'code':'WorkingCampaignStopped'})
            self.sessions.begin_close(self.turn, failure)
        self.sessions.finish_close(self.turn)

    def run_normal(self, adapter):
        context = self.observation_context(self.case['input_profile'])
        observation = self.runtime.generate_with_llm(self.tokens['interaction'],context,adapter,identity='WorkingObservation')
        review = self.runtime.validate_with_llm(self.tokens['interaction'],observation,adapter)
        outcome = self.runtime.commit(self.tokens['interaction'],observation,review.identity)
        if outcome.status != 'Committed': raise ContractError('WorkingObservationRejected:'+outcome.reason)
        context = self.policy_context(outcome.committed)
        policy = self.runtime.generate_with_llm(self.tokens['interaction'],context,adapter,identity='WorkingPolicy')
        review = self.runtime.validate_with_llm(self.tokens['interaction'],policy,adapter)
        outcome = self.runtime.commit(self.tokens['interaction'],policy,review.identity)
        self.sessions.policy_result(self.turn,policy,outcome)
        if outcome.status != 'Committed': raise ContractError('WorkingPolicyRejected:'+outcome.reason)
        utility = self.policy_runtime.utility_review(self.tokens['interaction'],policy,adapter)
        if self.h.get(utility).payload['status'] != 'PASS': raise ContractError('WorkingUtilityNotPass')
        if policy.record.payload['outcome'] == 'Execute':
            self.allow_reads()
            intent = self.actions.create_intent(self.tokens['interaction'],policy.record.ref,
                                               expires_at=self.h.clock.now+1000,idempotency_key='working-effect')
            self.sessions.bind_intent(self.turn,intent)
            result = self.actions.execute(self.tokens['interaction'],intent)
            self.sessions.effect_result(self.turn,result)
            if self.h.get(result).payload['status'] != 'Occurred': raise ContractError('WorkingEffectNotOccurred')
        self.sessions.settle(self.turn)
        return {'observation_digest':digest(observation),'policy_digest':digest(policy),'outcome':policy.record.payload['outcome']}

    def run_control(self, spec, adapter):
        if spec['kind'] == 'Observation':
            context = self.observation_context('work')
            payload = spec['candidate']
        else:
            context = self.policy_context(self.fixed_observation)
            payload = {**self.config['policy_control_base'], **spec['changes'],
                       'context_refs':[json_value(self.input)]}
        candidate = self.runtime.propose(context,'WorkingPolicy' if spec['kind']=='PolicyOutcome' else 'WorkingObservation','r1',payload)
        review = self.runtime.validate_with_llm(self.tokens['interaction'],candidate,adapter)
        if review.status != spec['expected_semantic']: raise ContractError('WorkingControlUnexpectedSemantic:'+review.status)
        details = json.loads(review.details_json)
        checks = {c['id']:c['status'] for c in details.get('checks',[])}
        if spec['id'] == 'P1-localization-conflict' and not any(checks.get(r)=='FAIL' for r in ('S3','S5')):
            raise ContractError('WorkingControlTargetNotIdentified')
        if spec['id'] == 'P3-unsupported-uncertainty' and checks.get('S2') != 'FAIL':
            raise ContractError('WorkingControlTargetNotIdentified')
        if spec['kind'] == 'Observation':
            execution = self.h.get(review.execution).payload
            boundary = next((r['status'] for r in details.get('criteria',[]) if r['id']=='boundary'),None)
            if boundary != 'FAIL' and execution.get('responsibility_result',{}).get('status') != 'FAIL':
                raise ContractError('WorkingControlTargetNotIdentified')
        utility = None
        if spec['kind'] == 'PolicyOutcome':
            utility = self.h.get(self.policy_runtime.utility_review(self.tokens['interaction'],candidate,adapter)).payload['status']
            if utility != spec['expected_utility']: raise ContractError('WorkingControlUnexpectedUtility:'+utility)
        # No control candidate enters formal state, and no control effect is attempted.
        self.close_failure()
        return {'candidate_digest':digest(candidate),'semantic_status':review.status,'utility_status':utility,
                'review':json.loads(review.details_json),'required_detection_pending_content_review':True}


def run_batch(config, adapter, recorder_factory, *, clock=time.monotonic, before_case=lambda spec:None):
    limited = CallBudget(adapter,config['budget'],clock)
    specs = config['fixed_review_controls'] + config['normal_cases']
    normals = {c['id']:c for c in config['normal_cases']}
    rows, stop = [], None
    for spec in specs:
        row = {'id':spec['id'],'execution':'NOT_RUN'}
        if stop is None:
            before_case(spec)
            limit = spec.get('max_calls',config['budget']['normal_case_max_calls'])
            limited.begin_case(limit)
            evidence = recorder_factory(spec['id'])
            world, start = None, len(adapter.records)
            try:
                world = WorkingWorld(evidence,config,normals[spec['source_case']] if 'source_case' in spec else spec,
                                     fixed_control='source_case' in spec)
                details = world.run_control(spec,limited) if 'source_case' in spec else world.run_normal(limited)
                row.update(execution='COMPLETED',**details)
            except (ContractError,ModelFailure,AccessDenied) as exc:
                stop = type(exc).__name__ + ':' + str(exc)
                row.update(execution='FAILED',reason=stop)
                if world is not None: world.close_failure()
            finally:
                for record in adapter.records[start:]: evidence.emit('model_execution',**record)
                if world is not None: evidence.capture(world.h,'working-final')
                evidence.close()
                row['calls'] = len(adapter.records)-start
        rows.append(row)
    return {'rows':rows,'stop_reason':stop,'calls':adapter.calls-limited.initial,
            'content_review_required':True,'semantic_support_claimed':False}
