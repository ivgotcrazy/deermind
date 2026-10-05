"""Trusted synchronous activity controller; transitions never correct old facts."""
from uuid import uuid4

from .actions import ActionRuntime, exact_ref
from .records import Dependency, Mode, Record, Ref, Role, Space, json_value
from .runtime import ContractError
from .security import AccessDenied


class ActivityRuntime(ActionRuntime):
    def execute(self, token, intent_ref, *, mode='OCCUR_FULL'):
        intent = self.h.get(intent_ref)
        if intent is None or intent.kind != 'ActionIntent' or intent_ref.space != Space.EXECUTION:
            raise ContractError('ExactIntentRequired')
        p = intent.payload
        if p['executor_target'] != 'activity-control':
            raise ContractError('ControlExecutorMismatch')
        previous = next((r for r in self.h.executions.records(intent.subject)
                         if r.kind == 'ActionExecutionResult' and r.payload['intent_ref'] == json_value(intent_ref)), None)
        if previous:
            self.security.read(token, previous.ref, p['purpose'], 'reasoning-runtime', intent_ref, ('ActionExecutionResult',))
            return previous.ref
        if mode not in ('OCCUR_FULL', 'NOT_OCCURRED'):
            raise ContractError('UnknownControlEffectMode')
        status, reason, occurrence = 'NotOccurred', '', None
        try:
            self._authorize(token, p, intent_ref)
            if self.h.clock.now >= p['expires_at']:
                raise ContractError('IntentExpired')
            for ref in p['preconditions']:
                self._current(token, exact_ref(ref), p['scope'], p['purpose'])
            action, _ = self.security.read(token, exact_ref(p['action_semantic_ref']), p['purpose'],
                                          'reasoning-runtime', intent_ref, ('ActionSemantic',))
            transition = action.payload['activity_transition']
            prior = exact_ref(transition['from_ref'])
            old, _ = self.security.read(token, prior, p['purpose'], 'reasoning-runtime', intent_ref,
                                       ('ActivityState', 'ActivityTransitionOccurred'))
            self._current(token, prior, p['scope'], p['purpose'])
            policy = self.h.get(exact_ref(p['policy_ref']))
            if (old.payload['activity_purpose'] != transition['from'] or p['episode'] != old.payload['episode']
                    or not any(d.target == prior and d.mode == Mode.CURRENT for d in policy.dependencies)):
                raise ContractError('ControlActivityBindingMismatch')
        except (ContractError, AccessDenied) as exc:
            reason = str(exc)
        else:
            if mode == 'NOT_OCCURRED':
                reason = 'MockControlRejected'
            else:
                self.h.clock.advance()
                ack = self._event('ControlAcknowledgement', intent.subject, {
                    'intent_ref': json_value(intent_ref), 'previous_activity_ref': json_value(prior),
                    'activity_purpose': transition['to'], 'episode': transition['episode'],
                    'task_ref': transition['task_ref'], 'source': 'TRUSTED-MOCK-CONTROL'})
                record = Record.create(ref=Ref(Space.FACT, uuid4().hex, '1'), kind='ActivityTransitionOccurred',
                    subject=intent.subject, owner='Interaction', scope=p['scope'], purpose=p['purpose'],
                    recorded_at=self.h.clock.now, occurrence_key='control:' + intent_ref.identity,
                    payload={**self.h.get(ack).payload, 'acknowledgement_ref': json_value(ack)},
                    dependencies=(Dependency(prior, Mode.PINNED, Role.FACTUAL),
                                  Dependency(intent_ref, Mode.PINNED, Role.OPERATIONAL),
                                  Dependency(ack, Mode.PINNED, Role.FACTUAL)),
                    provenance=('mock-control-factual-admission', ack.identity))
                self.h.facts.append(record)
                occurrence, status = record.ref, 'Occurred'
        return self._event('ActionExecutionResult', intent.subject, {
            'intent_ref': json_value(intent_ref), 'status': status, 'reason': reason,
            'occurrence_ref': json_value(occurrence) if occurrence else None})
