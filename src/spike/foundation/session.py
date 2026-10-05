"""In-memory, per-conversation serial turns through terminal action-result handling."""
from .boundary import digest
from .records import Ref, Space, json_value
from .runtime import ContractError


class SerialSession:
    def __init__(self, boundary):
        self.b = boundary
        self.queues = {}
        self.active = {}
        self.turns = {}
        self.scopes = {}

    def _event(self, kind, turn=None, **data):
        self.b.h.clock.advance()
        subject = self.turns[turn]['subject'] if turn else data.pop('subject')
        return self.b.execution(kind, subject, {'turn_ref': json_value(turn) if turn else None, **data})

    def enqueue(self, conversation, input_ref):
        record = self.b.h.get(input_ref)
        if record is None or input_ref.space != Space.FACT or record.kind != 'CurrentInteractionInput':
            raise ContractError('ReceivedInputFactRequired')
        queue = self.queues.setdefault(conversation, [])
        if any(r == input_ref for values in self.queues.values() for r in values) or any(t['input'] == input_ref for t in self.turns.values()):
            raise ContractError('InputAlreadyEnqueued')
        scope = (record.subject, record.scope, record.purpose)
        if self.scopes.setdefault(conversation, scope) != scope:
            raise ContractError('ConversationScopeMismatch')
        queue.append(input_ref)
        return self._event('InputQueued', subject=record.subject, conversation=conversation, input_ref=json_value(input_ref))

    def start(self, conversation):
        if conversation in self.active:
            raise ContractError('ConversationTurnActive')
        queue = self.queues.get(conversation, [])
        if not queue:
            raise ContractError('NoQueuedInput')
        input_ref = queue.pop(0)
        record = self.b.h.get(input_ref)
        ref = self._event('TurnStarted', subject=record.subject, conversation=conversation, input_ref=json_value(input_ref))
        self.turns[ref] = {'subject': record.subject, 'scope': record.scope, 'purpose': record.purpose,
                           'conversation': conversation, 'input': input_ref, 'phase': 'INPUT'}
        self.active[conversation] = ref
        return ref

    def require(self, turn, phase):
        t = self.turns.get(turn)
        if t is None or self.active.get(t['conversation']) != turn or t['phase'] != phase:
            raise ContractError('TurnPhaseMismatch')
        return t

    def bind_context(self, turn, context):
        t = self.require(turn, 'INPUT')
        if self.b._contexts.get(context.identity) != context:
            raise ContractError('RegisteredContextRequired')
        refs = {i.record.ref for i in context.items}
        if (context.subject, context.scope, context.purpose) != (t['subject'], t['scope'], t['purpose']) or t['input'] not in refs:
            raise ContractError('TurnContextInputMismatch')
        if any(r in refs for r in self.queues.get(t['conversation'], [])):
            raise ContractError('QueuedInputInActiveContext')
        t.update(phase='POLICY', context_id=context.identity)
        self._event('TurnContextBound', turn, context_id=context.identity, input_ref=json_value(t['input']))

    def policy_result(self, turn, candidate, outcome):
        t = self.require(turn, 'POLICY')
        audit = self.b.h.get(outcome.audit_ref)
        if (candidate.context_id != t['context_id'] or outcome.candidate_digest != digest(candidate)
                or audit is None or audit.kind != 'CommitOutcome'
                or audit.payload.get('candidate_digest') != digest(candidate)
                or audit.payload.get('status') != outcome.status
                or audit.payload.get('committed') != (json_value(outcome.committed) if outcome.committed else None)):
            raise ContractError('TurnCommitBindingMismatch')
        execute = outcome.status == 'Committed' and candidate.record.payload['outcome'] == 'Execute'
        t.update(phase='INTENT' if execute else 'READY', policy_ref=candidate.record.ref)
        self._event('TurnPolicyResult', turn, candidate_digest=digest(candidate), commit_ref=json_value(outcome.audit_ref),
                    policy_ref=json_value(candidate.record.ref), status=outcome.status)

    def bind_intent(self, turn, intent_ref):
        t = self.require(turn, 'INTENT')
        intent = self.b.h.get(intent_ref)
        if intent is None or intent.kind != 'ActionIntent' or intent.payload['policy_ref'] != json_value(t['policy_ref']):
            raise ContractError('TurnIntentBindingMismatch')
        t.update(phase='EFFECT', intent_ref=intent_ref)
        self._event('TurnIntentBound', turn, intent_ref=json_value(intent_ref))

    def effect_result(self, turn, result_ref):
        t = self.require(turn, 'EFFECT')
        result = self.b.h.get(result_ref)
        if (result is None or result.kind != 'ActionExecutionResult'
                or result.payload['intent_ref'] != json_value(t['intent_ref'])
                or result.payload['status'] not in ('Occurred', 'NotOccurred', 'Indeterminate')):
            raise ContractError('TurnActionResultBindingMismatch')
        t.update(phase='READY', result_ref=result_ref)
        self._event('ActionResultProcessed', turn, result_ref=json_value(result_ref), status=result.payload['status'])

    def continue_cycle(self, turn):
        """Only an acknowledged Control effect can start another cycle in this turn."""
        from .actions import exact_ref
        t = self.require(turn, 'READY')
        result = self.b.h.get(t['result_ref']) if 'result_ref' in t else None
        intent = self.b.h.get(t['intent_ref']) if 'intent_ref' in t else None
        occurrence = self.b.h.get(exact_ref(result.payload['occurrence_ref'])) if result and result.payload.get('occurrence_ref') else None
        if (not result or not intent or intent.payload['executor_target'] != 'activity-control'
                or result.payload['status'] != 'Occurred' or not occurrence
                or occurrence.ref.space != Space.FACT or occurrence.kind != 'ActivityTransitionOccurred'
                or occurrence.payload['intent_ref'] != json_value(intent.ref)):
            raise ContractError('SuccessfulControlRequired')
        self._event('DecisionCycleContinued', turn, result_ref=json_value(result.ref), activity_ref=json_value(occurrence.ref))
        for key in ('result_ref', 'intent_ref', 'policy_ref', 'context_id'):
            t.pop(key, None)
        t['phase'] = 'INPUT'

    def settle(self, turn):
        t = self.require(turn, 'READY')
        self._event('TurnSettled', turn, conversation=t['conversation'])
        t['phase'] = 'SETTLED'
        del self.active[t['conversation']]
