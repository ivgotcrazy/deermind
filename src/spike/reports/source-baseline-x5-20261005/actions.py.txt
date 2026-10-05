"""Exact mock effects and on-demand factual exposure reconstruction.

No natural-language classification or durable exposure model lives here.
Mock acknowledgements are trusted test controls, not learner/model tool arguments.
"""
from uuid import uuid4

from .records import Dependency, Mode, Record, Ref, Role, Space, json_value
from .runtime import ContractError, CurrentResolver
from .security import AccessDenied, DataUse, Operation, parameter


def exact_ref(value):
    return Ref(Space(value['space']), value['identity'], value['revision'])


class ActionRuntime:
    def __init__(self, boundary):
        self.runtime = boundary
        self.h, self.security = boundary.h, boundary.security

    def _event(self, kind, subject, payload):
        return self.runtime.execution(kind, subject, payload)

    def _authorize(self, token, payload, source):
        action = exact_ref(payload['action_semantic_ref'])
        request = Operation(payload['purpose'], payload['subject'], action.identity, 'execute',
                            tuple(parameter(k, payload[k]) for k in ('exact_payload', 'executor_target', 'action_semantic_ref')))
        return self.security.enforce(token, request, source,
            DataUse(payload['purpose'], payload['subject'], 'ActionDisclosure', 'execute',
                    payload['executor_target'], disclosure='learner'))

    def _current(self, token, ref, scope, purpose):
        result = CurrentResolver(self.h.capture(), self.runtime._eligibility(token, 'reasoning-runtime')).resolve_exact(ref, scope, purpose)
        if result.current is None:
            raise ContractError('EffectPrecondition:' + result.reason)

    def create_intent(self, token, policy_ref, *, expires_at, idempotency_key):
        policy = self.h.get(policy_ref)
        if (policy is None or policy_ref.space != Space.DERIVED or policy.kind != 'PolicyOutcome'
                or policy.owner != 'Interaction'):
            raise ContractError('CommittedPolicyRequired')
        commits = [r for r in self.h.audit.records() if r.kind == 'CommitOutcome'
                   and r.payload.get('committed') == json_value(policy_ref) and r.payload.get('status') == 'Committed']
        if not commits:
            raise ContractError('FormalPolicyCommitRequired')
        source = self._event('ActionIntentAdmission', policy.subject, {'policy_ref': json_value(policy_ref)})
        self.security.read(token, policy_ref, policy.purpose, 'reasoning-runtime', source, ('PolicyOutcome',))
        self._current(token, policy_ref, policy.scope, policy.purpose)
        p = policy.payload
        if p.get('outcome') != 'Execute':
            raise ContractError('ExecuteOutcomeRequired')
        action = Ref(Space.CANONICAL, p['action_identity'], p['action_revision'])
        semantic, _ = self.security.read(token, action, policy.purpose, 'reasoning-runtime', source, ('ActionSemantic',))
        self._current(token, action, policy.scope, policy.purpose)
        if not any(d.target == action and d.mode == Mode.CURRENT for d in policy.dependencies):
            raise ContractError('ActionSemanticNotBoundToPolicy')
        if (type(expires_at) is not int or expires_at <= self.h.clock.now
                or not isinstance(idempotency_key, str) or not idempotency_key
                or not isinstance(p.get('exact_payload'), str) or not p['exact_payload']
                or p.get('executor_target') != semantic.payload['executor_target']):
            raise ContractError('InvalidIntentParameters')
        payload = {'policy_ref': json_value(policy_ref), 'action_semantic_ref': json_value(action),
                   'exact_payload': p['exact_payload'], 'executor_target': p['executor_target'],
                   'subject': policy.subject, 'scope': policy.scope, 'purpose': policy.purpose,
                   'episode': p['episode'], 'expires_at': expires_at, 'idempotency_key': idempotency_key,
                   # This minimal profile explicitly declares the whole policy basis effect-critical.
                   'preconditions': [json_value(policy_ref), json_value(action)]}
        authority, data = self._authorize(token, payload, source)
        payload.update(authority_basis=list(authority.authority_basis), data_authority_basis=list(data.authority_basis))
        for old in self.h.executions.records(policy.subject):
            if old.kind != 'ActionIntent':
                continue
            prior = old.payload
            if (prior['scope'], prior['purpose'], prior['idempotency_key']) == (policy.scope, policy.purpose, idempotency_key):
                if prior != payload:
                    raise ContractError('IdempotencyKeyConflict')
                return old.ref
        return self._event('ActionIntent', policy.subject, payload)

    def execute(self, token, intent_ref, *, mode='OCCUR_FULL', partial_characters=None):
        intent = self.h.get(intent_ref)
        if intent is None or intent.kind != 'ActionIntent' or intent_ref.space != Space.EXECUTION:
            raise ContractError('ExactIntentRequired')
        p = intent.payload
        # Existing terminal results are read, never re-executed (including Indeterminate).
        previous = next((r for r in self.h.executions.records(intent.subject)
                         if r.kind == 'ActionExecutionResult' and r.payload['intent_ref'] == json_value(intent_ref)), None)
        if previous:
            self.security.read(token, previous.ref, p['purpose'], 'reasoning-runtime', intent_ref, ('ActionExecutionResult',))
            return previous.ref
        if mode not in ('OCCUR_FULL', 'OCCUR_PARTIAL', 'NOT_OCCURRED', 'INDETERMINATE'):
            raise ContractError('UnknownMockEffectMode')
        if mode == 'OCCUR_PARTIAL' and (type(partial_characters) is not int or not 0 < partial_characters < len(p['exact_payload'])):
            raise ContractError('InvalidPartialAcknowledgement')
        status, reason, occurrence = 'NotOccurred', '', None
        try:
            self._authorize(token, p, intent_ref)
            if self.h.clock.now >= p['expires_at']:
                raise ContractError('IntentExpired')
            for ref in p['preconditions']:
                self._current(token, exact_ref(ref), p['scope'], p['purpose'])
        except (ContractError, AccessDenied) as exc:
            reason = str(exc)
        else:
            self.h.clock.advance()
            if mode == 'NOT_OCCURRED':
                reason = 'MockTransportRejected'
            elif mode == 'INDETERMINATE':
                status, reason = 'Indeterminate', 'MockAcknowledgementUnavailable'
            else:
                actual = p['exact_payload'] if mode == 'OCCUR_FULL' else p['exact_payload'][:partial_characters]
                acknowledgement = self._event('DisplayAcknowledgement', intent.subject, {
                    'intent_ref': json_value(intent_ref), 'actual_payload': actual,
                    'completeness': 'FULL' if mode == 'OCCUR_FULL' else 'PARTIAL',
                    'rendered_at': self.h.clock.now, 'executor_target': p['executor_target'],
                    'source': 'TRUSTED-MOCK-DISPLAY'})
                ack = self.h.get(acknowledgement).payload
                record = Record.create(ref=Ref(Space.FACT, uuid4().hex, '1'), kind='ActionOccurrence',
                    subject=intent.subject, owner='Interaction', scope=p['scope'], purpose=p['purpose'],
                    recorded_at=self.h.clock.now, occurrence_key='action:' + intent_ref.identity,
                    payload={'intent_ref': json_value(intent_ref), 'acknowledgement_ref': json_value(acknowledgement),
                             'episode': p['episode'], 'result': 'Occurred',
                             'actual_disclosure': {'payload': ack['actual_payload'], 'completeness': ack['completeness'],
                                                   'rendered_at': ack['rendered_at']}},
                    dependencies=(Dependency(intent_ref, Mode.PINNED, Role.OPERATIONAL),
                                  Dependency(acknowledgement, Mode.PINNED, Role.FACTUAL)),
                    provenance=('mock-display-factual-admission', acknowledgement.identity))
                self.h.facts.append(record)
                occurrence, status = record.ref, 'Occurred'
        return self._event('ActionExecutionResult', intent.subject, {
            'intent_ref': json_value(intent_ref), 'status': status, 'reason': reason,
            'occurrence_ref': json_value(occurrence) if occurrence else None})

    def exposure_for(self, token, response_ref):
        response = self.h.get(response_ref)
        if response is None or response.kind != 'LearnerWorkSubmitted':
            raise ContractError('ResponseRequired')
        source = self._event('ExposureReconstruction', response.subject, {'response_ref': json_value(response_ref)})
        response, _ = self.security.read(token, response_ref, response.purpose, 'exposure-runtime', source, ('LearnerWorkSubmitted',))
        episode = response.payload['episode']
        result = {'response_ref': json_value(response_ref), 'episode': episode, 'exposures': [], 'unconfirmed': [],
                  'learner_used_assistance': 'NOT_INFERRED', 'source': 'ON-DEMAND-FACTUAL-LINEAGE'}
        intents = [r for r in self.h.executions.records(response.subject) if r.kind == 'ActionIntent'
                   and r.payload['episode'] == episode and r.payload['scope'] == response.scope and r.payload['purpose'] == response.purpose]
        for intent in intents:
            self.security.read(token, intent.ref, response.purpose, 'exposure-runtime', source, ('ActionIntent',))
            terminal = next((r for r in self.h.executions.records(response.subject) if r.kind == 'ActionExecutionResult'
                             and r.payload['intent_ref'] == json_value(intent.ref)), None)
            if terminal is None:
                result['unconfirmed'].append({'intent_ref': json_value(intent.ref), 'status': 'Pending'})
                continue
            self.security.read(token, terminal.ref, response.purpose, 'exposure-runtime', source, ('ActionExecutionResult',))
            t = terminal.payload
            if t['status'] != 'Occurred':
                result['unconfirmed'].append({'intent_ref': json_value(intent.ref), 'status': t['status']})
                continue
            occurrence, _ = self.security.read(token, exact_ref(t['occurrence_ref']), response.purpose,
                                                'exposure-runtime', source, ('ActionOccurrence',))
            actual = occurrence.payload['actual_disclosure']
            ack, _ = self.security.read(token, exact_ref(occurrence.payload['acknowledgement_ref']), response.purpose,
                                         'exposure-runtime', source, ('DisplayAcknowledgement',))
            if (occurrence.payload['intent_ref'] != json_value(intent.ref) or ack.payload['intent_ref'] != json_value(intent.ref)
                    or actual != {'payload': ack.payload['actual_payload'], 'completeness': ack.payload['completeness'], 'rendered_at': ack.payload['rendered_at']}):
                raise ContractError('DisclosureLineageMismatch')
            result['exposures'].append({'occurrence_ref': json_value(occurrence.ref), 'intent_ref': json_value(intent.ref),
                'acknowledgement_ref': json_value(ack.ref), **actual,
                'before_response': actual['rendered_at'] < response.recorded_at})
        result['exposures'].sort(key=lambda x: (x['rendered_at'], x['occurrence_ref']['identity']))
        return result
