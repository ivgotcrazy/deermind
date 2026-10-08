"""One fixed task, isolated authority, two serial turns and factual help history.

This entry reuses the existing boundary, protocols and synchronous mock executor.
It does not inherit the historical scenario worlds or their scripted cognition.
"""
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
import json
import time

from .actions import ActionRuntime, exact_ref
from .boundary import BoundaryRuntime, ContextInput, Protocol, digest
from .cases import seed
from .llm import ModelFailure
from .records import Ref, Role, Space, VersionContext, json_value
from .runtime import Compatibility, ContractError, Decision, Harness
from .security import (AccessDenied, AuthorityGrant, CredentialBinding, DataUseGrant,
                       SecurityRuntime, parameter)
from .working_campaign import CallBudget
from .working_entry import RestrictedEntry, WorkingScope

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / 'src/spike/fixtures/single-task-prototype-v1.json'
RECEIPTS = {
    'NoIntervention': '本轮没有新增提示。',
    'Defer': '等待后续作答。',
    'FAILED': '本轮处理失败，可重新提交。',
    'BLOCKED': '本轮尚未收束，后续作答已排队。',
}


def load_plan():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    if ([s['id'] for s in plan['sessions']] != [f'T{i:02d}' for i in range(1, 13)]
            or any(len(s['inputs']) != 2 for s in plan['sessions'])
            or plan['budget'] != {'max_calls': 168, 'wall_time_seconds': 2700,
                                  'turn_max_calls': 7, 'transport_retries': 0}):
        raise ContractError('InvalidSingleTaskPlan')
    return plan


class InvariantViolation(ContractError):
    """Observed mechanical violation, not a model quality judgment."""


class SingleTaskEntry(RestrictedEntry):
    def __init__(self, world, profile):
        self.world = world
        super().__init__(world.runtime, profile)

    def check_context(self, context):
        super().check_context(context)
        expected = self.world.context_sources.get(context.identity)
        if expected is None or tuple(i.record.ref for i in context.items) != expected:
            raise ContractError('SingleTaskSourceContractMismatch')
        for item in context.items:
            record = item.record
            if record.kind in ('LearnerWorkSubmitted', 'CurrentInteractionInput'):
                if record.payload.get('episode') != self.world.episode:
                    raise ContractError('SingleTaskConversationMismatch')
            if record.kind == 'AssistanceContext':
                if record.ref not in self.world.help_views:
                    raise ContractError('UnregisteredAssistanceProjection')
                if record.payload != self.world.help_payloads[record.ref]:
                    raise ContractError('AssistanceProjectionChanged')


class SingleTaskWorld:
    def __init__(self, evidence, conversation, plan):
        self.e, self.conversation, self.plan = evidence, conversation, plan
        self.h = Harness()
        self.security = SecurityRuntime(self.h)
        self.runtime = BoundaryRuntime(self.h, self.security)
        self.actions = ActionRuntime(self.runtime)
        self.token = self.security.issue_fixture_credential(
            CredentialBinding('interaction', 'learning', 'learner-A', 100000))
        self.endpoint = plan['model']['base_url']
        self.episode = 'single-task-' + conversation
        self.protocols, self.versions = {}, {}
        self.context_sources, self.help_views, self.help_payloads, self.received = {}, {}, {}, {}
        self.turn = None
        self.rows = []
        self.action_refs = tuple(seed(self.h, Ref(Space.CANONICAL, name, 'e1-v1'),
            kind='ActionSemantic', payload={'action_identity': name, 'action_revision': 'e1-v1',
                'exact_payload': payload, 'executor_target': 'mock-display'})
            for name, payload in plan['actions'].items())
        self.constraints = seed(self.h, Ref(Space.CANONICAL, 'SingleTaskActivity', 'v1'),
            kind='ActivityConstraints', payload={'episode': self.episode,
                'purpose': 'IndependentDiagnosisWithLimitedHelp',
                'allowed_action_refs': [json_value(r) for r in self.action_refs],
                'reason': 'Only registered local hints. No full solution, activity transition or new task.'})
        for role, file in plan['protocols'].items():
            definition = json.loads((ROOT / file).read_text(encoding='utf-8'))
            ref = seed(self.h, Ref(Space.CANONICAL, definition['identity'], definition['version']),
                       kind='ReasoningProtocol', payload=definition)
            policy = role == 'policy'
            rule = seed(self.h, Ref(Space.CANONICAL,
                'E1PolicySemanticRules' if policy else 'SingleTaskWorkRules', definition['version']),
                kind='SemanticValidationRules', payload={'system': definition['validation_system'],
                    'format': definition.get('validation_format', 'legacy-v1'),
                    **({} if policy else {'criteria': definition['criteria']})})
            bindings = (ref, rule)
            if policy:
                utility = seed(self.h, Ref(Space.CANONICAL, 'E1UtilityRules', 'v2'),
                    kind='PolicyUtilityRules', payload={'system': definition['utility_system'],
                        'rubric': definition['utility_rubric'], 'test_only': True})
                bindings += (utility,)
                required = definition['runtime_binding_requirement']
                if any(required[k] != json_value(v) for k, v in
                       [('protocol_ref', ref), ('semantic_rule_ref', rule), ('utility_rule_ref', utility)]):
                    raise ContractError('PolicyDeclaredBindingMismatch')
            kind = 'PolicyOutcome' if policy else 'Observation'
            kinds = ('LearnerWorkSubmitted', 'CurrentInteractionInput', 'AssistanceContext')
            if policy:
                kinds += ('Observation', 'ActivityConstraints', 'ActionSemantic')
            fields = tuple(tuple(f) for f in definition['fields']) if policy else (('description', 'string'),)
            protocol = Protocol(ref, kind, 'Interaction', kinds, fields, rule, self.endpoint)
            self.runtime.register_protocol(protocol)
            compatibility = 'single-task-' + role + '-v1'
            self.h.canonical.add_compatibility_fixture(Compatibility(
                compatibility, bindings, 'learner-A', 'learning', Decision.ALLOW))
            self.protocols[role] = protocol
            self.versions[role] = VersionContext(bindings, compatibility_basis=compatibility)
            self.grant_authority(role + '-reason', (ref.identity,), ('reason', 'validate'))
            identities = tuple(self.identity(role, i) for i in (1, 2))
            self.grant_authority(role + '-commit', identities, ('commit',),
                {'owner': 'Interaction', 'kind': kind})
            self.grant_data(role + '-validate', (kind,), ('validate',), (self.endpoint,))
            self.grant_data(role + '-commit', (kind,), ('commit',), ('formal-state',))
        for ref in self.action_refs:
            action = self.h.get(ref).payload
            self.grant_authority('effect-' + ref.identity, (ref.identity,), ('execute',),
                {'exact_payload': action['exact_payload'], 'executor_target': 'mock-display',
                 'action_semantic_ref': json_value(ref)})
        self.grant_data('display', ('ActionDisclosure',), ('execute',), ('mock-display',), disclosure='learner')
        model_kinds = ('LearnerWorkSubmitted', 'CurrentInteractionInput', 'AssistanceContext',
                      'Observation', 'ActionSemantic', 'ActivityConstraints', 'ReasoningProtocol',
                      'SemanticValidationRules', 'PolicyUtilityRules')
        self.grant_data('model-read', model_kinds, ('read',), (self.endpoint,))
        self.grant_data('local-read', model_kinds + ('PolicyOutcome', 'ActionIntent',
            'ActionExecutionResult', 'ActionOccurrence', 'DisplayAcknowledgement'),
            ('read',), ('reasoning-runtime', 'exposure-runtime'))
        profile = WorkingScope('SingleTaskPrototype', 'v1', 'learner-A', 'learner-A', 'learning',
            tuple(p.ref for p in self.protocols.values()), self.constraints, self.action_refs)
        self.entry = SingleTaskEntry(self, profile)
        self.sessions = self.entry.session
        self.allow_reads()
        self.e.emit('single_task_setup', conversation=conversation, grants=self.security.describe_grants(),
                    scripted_cognition=False, evaluation_capability=False, display='TRUSTED-MOCK')

    def identity(self, role, number):
        return f'SingleTask-{self.conversation}-{role}-{number}'

    def grant_authority(self, name, resources, operations, constraints=None):
        self.security.install_authority(AuthorityGrant(name, 'interaction', 'learning', 'learner-A',
            resources, operations, 100000, tuple((k, (parameter(k, v)[1],))
                                               for k, v in (constraints or {}).items())))

    def grant_data(self, name, kinds, operations, destinations, disclosure='internal'):
        self.security.install_data(DataUseGrant('data-' + name, 'interaction', 'learning', 'learner-A',
            kinds, operations, destinations, 'run', disclosure, 100000))

    def allow_reads(self):
        kinds = {'LearnerWorkSubmitted', 'CurrentInteractionInput', 'AssistanceContext', 'Observation',
                 'PolicyOutcome', 'ActionSemantic', 'ActivityConstraints', 'ReasoningProtocol',
                 'SemanticValidationRules', 'PolicyUtilityRules', 'ActionIntent',
                 'ActionExecutionResult', 'ActionOccurrence', 'DisplayAcknowledgement'}
        refs = tuple(r.ref.identity for space in Space for r in self.h.history_for(space).records()
                     if r.kind in kinds and r.subject == 'learner-A' and r.scope == 'learner-A')
        self.grant_authority('read-' + uuid4().hex, refs, ('read',))

    def receive(self, text, *, conversation=None, task=None):
        if ((conversation is not None and conversation != self.conversation)
                or (task is not None and task != self.plan['task']['identity'])):
            raise ContractError('SingleTaskInputScopeMismatch')
        if not isinstance(text, str) or not text.strip() or len(self.received) >= 2:
            raise ContractError('InvalidSingleTaskInput')
        number = len(self.received) + 1
        common = {'text': text, 'episode': self.episode, 'conversation': self.conversation,
                  'task_identity': self.plan['task']['identity'], 'input_purpose': 'submitted-work'}
        work = seed(self.h, Ref(Space.FACT, self.identity('work-input', number), '1'),
            kind='LearnerWorkSubmitted', occurrence_key=self.identity('work-input', number),
            payload={'text': text, 'task': self.plan['task']['question'], 'episode': self.episode})
        received = seed(self.h, Ref(Space.FACT, self.identity('received', number), '1'),
            kind='CurrentInteractionInput', occurrence_key=self.identity('received', number), payload=common)
        self.received[received] = {'work': work, 'number': number}
        self.sessions.enqueue(self.conversation, received)
        self.e.emit('input_received', input_ref=json_value(received), work_ref=json_value(work), text=text)
        return received

    def start(self):
        self.turn = self.sessions.start(self.conversation)
        received = self.sessions.turns[self.turn]['input']
        self.input = received
        self.work = self.received[received]['work']
        self.number = self.received[received]['number']
        self.allow_reads()
        exposure = self.actions.exposure_for(self.token, self.work)
        # Keep the full intent/ack lineage in the audit; the model needs the exact
        # disclosure and its occurrence reference, not three copies of that chain.
        visible = {'exposures': [{k: v for k, v in x.items()
                    if k not in ('intent_ref', 'acknowledgement_ref')} for x in exposure['exposures']],
                   'unconfirmed': exposure['unconfirmed'],
                   'learner_used_assistance': exposure['learner_used_assistance']}
        # A single exact source field avoids repeating nested lineage fields in
        # the existing source-handle registry. No semantic assertion is rewritten.
        payload = {'history': json.dumps(visible, ensure_ascii=False, separators=(',', ':'))}
        self.help = self.runtime.execution('AssistanceContext', 'learner-A', payload)
        self.help_views[self.help] = exposure
        self.help_payloads[self.help] = payload
        self.allow_reads()
        self.e.emit('turn_started', number=self.number, turn_ref=json_value(self.turn), assistance=exposure)
        return self.turn

    def context(self, role, observation=None):
        # The work fact retains the entire unclassified work/request text.
        refs = (self.work, self.help)
        if role == 'policy':
            record = self.h.get(observation) if observation else None
            if (record is None or record.kind != 'Observation'
                    or observation.identity != self.identity('work', self.number)):
                raise ContractError('CurrentCommittedObservationRequired')
            refs += (self.input, observation, self.constraints, *self.action_refs)
        self.allow_reads()
        context = self.runtime.assemble(self.token, self.protocols[role].ref,
            'learner-A', 'learner-A', 'learning', tuple(ContextInput(r,
                Role.CANONICAL if r.space == Space.CANONICAL else
                Role.FACTUAL if r.space == Space.FACT else
                Role.OPERATIONAL if r.space == Space.EXECUTION else Role.EPISTEMIC,
                current=r.space != Space.EXECUTION) for r in refs),
            self.versions[role])
        self.context_sources[context.identity] = refs
        if role == 'policy':
            self.sessions.bind_context(self.turn, context)
        else:
            self.sessions.bind_reasoning_context(self.turn, context)
        return context

    def reason(self, role, context, adapter, row):
        candidate = self.runtime.generate_with_llm(self.token, context, adapter,
                                                  identity=self.identity(role, self.number))
        row[role + '_candidate'] = json_value(candidate)
        review = self.runtime.validate_with_llm(self.token, candidate, adapter)
        row[role + '_review'] = json_value(review)
        outcome = self.runtime.commit(self.token, candidate, review.identity)
        row[role + '_commit'] = json_value(outcome)
        if role == 'policy':
            self.sessions.policy_result(self.turn, candidate, outcome)
        if outcome.status != 'Committed':
            raise ContractError(role + 'Rejected:' + outcome.reason)
        return candidate

    def close_failure(self, code):
        if self.turn is None or self.sessions.turns[self.turn]['phase'] == 'SETTLED':
            return True
        if self.sessions.turns[self.turn]['phase'] != 'CLOSING':
            failure = self.runtime.execution('TurnFailure', 'learner-A',
                {'turn_ref': json_value(self.turn), 'code': code})
            self.sessions.begin_close(self.turn, failure)
        try:
            self.sessions.finish_close(self.turn)
            return True
        except ContractError as exc:
            if str(exc) != 'EffectQuiescenceNotConfirmed':
                raise
            return False

    def process(self, adapter, *, effect_mode='OCCUR_FULL', partial_characters=None):
        # start() refuses another active turn before any understanding/model call.
        self.start()
        row = {'number': self.number, 'execution': 'STARTED', 'assistance': self.help_views[self.help],
               'displayed': [], 'receipt': None}
        initial = adapter.adapter.calls if isinstance(adapter, CallBudget) else adapter.calls
        try:
            observation = self.reason('work', self.context('work'), adapter, row)
            policy = self.reason('policy', self.context('policy', observation.record.ref), adapter, row)
            p = policy.record.payload
            row['outcome'] = p['outcome']
            if p['outcome'] == 'Execute':
                self.allow_reads()
                intent = self.actions.create_intent(self.token, policy.record.ref,
                    expires_at=self.h.clock.now + 1000, idempotency_key=self.identity('effect', self.number))
                self.sessions.bind_intent(self.turn, intent)
                result = self.actions.execute(self.token, intent, mode=effect_mode,
                                               partial_characters=partial_characters)
                self.sessions.effect_result(self.turn, result)
                row['effect'] = json_value(self.h.get(result))
                result_payload = self.h.get(result).payload
                if result_payload.get('occurrence_ref'):
                    occurrence = self.h.get(exact_ref(result_payload['occurrence_ref']))
                    row['displayed'].append(occurrence.payload['actual_disclosure'])
                if result_payload['status'] != 'Occurred' or any(
                        item['completeness'] != 'FULL' for item in row['displayed']):
                    raise ContractError('EffectNotFullyConfirmed')
            else:
                row['receipt'] = RECEIPTS[p['outcome']]
            self.sessions.settle(self.turn)
            row['execution'] = 'COMPLETED'
        except (ModelFailure, AccessDenied, ContractError) as exc:
            if isinstance(exc, InvariantViolation):
                raise
            row.update(execution='FAILED', reason=type(exc).__name__ + ':' + str(exc))
            settled = self.close_failure(row['reason'])
            row['receipt'] = RECEIPTS['FAILED' if settled else 'BLOCKED']
            row['session_blocked'] = not settled
        finally:
            final = adapter.adapter.calls if isinstance(adapter, CallBudget) else adapter.calls
            row['calls'] = final - initial
            row['turn_phase'] = self.sessions.turns[self.turn]['phase']
            self.rows.append(row)
            self.e.emit('turn_result', **row)
            self.e.capture(self.h, self.identity('final', self.number))
        self.check_invariants()
        return row

    def check_invariants(self):
        for record in self.h.states.records():
            if record.kind not in ('Observation', 'PolicyOutcome') or record.owner != 'Interaction':
                raise InvariantViolation('ForbiddenFormalWrite')
        for record in self.h.facts.records():
            if record.kind == 'ActionOccurrence':
                p = record.payload
                ack = self.h.get(exact_ref(p['acknowledgement_ref']))
                intent = self.h.get(exact_ref(p['intent_ref']))
                actual = p['actual_disclosure']
                if (not ack or not intent or intent.payload['exact_payload'] not in self.plan['actions'].values()
                        or ack.payload['intent_ref'] != p['intent_ref']
                        or actual['payload'] != ack.payload['actual_payload']
                        or actual['completeness'] != ack.payload['completeness']
                        or actual['rendered_at'] != ack.payload['rendered_at']
                        or actual['completeness'] not in ('FULL', 'PARTIAL')
                        or (actual['completeness'] == 'FULL' and actual['payload'] != intent.payload['exact_payload'])
                        or not intent.payload['exact_payload'].startswith(actual['payload'])):
                    raise InvariantViolation('InvalidActualDisclosure')


def run_batch(plan, adapter, recorder_factory, *, before_turn=lambda spec, number: None,
              clock=time.monotonic):
    budget = CallBudget(adapter, plan['budget'], clock)
    rows, stop = [], None
    for spec in plan['sessions']:
        row = {'id': spec['id'], 'family': spec['family'], 'turns': []}
        world, evidence = None, None
        try:
            if stop is None:
                evidence = recorder_factory(spec['id'])
                world = SingleTaskWorld(evidence, spec['id'], plan)
            for number, text in enumerate(spec['inputs'], 1):
                if stop is None and (clock() >= budget.deadline or adapter.calls - budget.initial >= plan['budget']['max_calls']):
                    stop = 'BudgetExhausted'
                if stop is not None or (world is not None and world.sessions.active):
                    row['turns'].append({'number': number, 'execution': 'NOT_RUN',
                                         'reason': stop or 'SessionNotSettled'})
                    continue
                before_turn(spec, number)
                budget.begin_case(plan['budget']['turn_max_calls'])
                world.receive(text)
                initial = len(adapter.records)
                try:
                    row['turns'].append(world.process(budget))
                finally:
                    for call in adapter.records[initial:]:
                        evidence.emit('model_execution', session=spec['id'], number=number, **call)
        except InvariantViolation as exc:
            stop = 'MechanicalViolation:' + str(exc)
        finally:
            if evidence is not None:
                evidence.capture(world.h, 'session-final') if world is not None else None
                evidence.close()
        while len(row['turns']) < 2:
            row['turns'].append({'number': len(row['turns']) + 1, 'execution': 'NOT_RUN', 'reason': stop})
        row['execution'] = ('COMPLETED' if all(t['execution'] == 'COMPLETED' for t in row['turns'])
                            else 'FAILED' if any(t['execution'] == 'FAILED' for t in row['turns']) else 'INCOMPLETE')
        rows.append(row)
    return {'rows': rows, 'stop_reason': stop, 'calls': adapter.calls - budget.initial,
            'content_review_required': True, 'semantic_support_claimed': False}
