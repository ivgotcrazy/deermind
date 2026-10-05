"""In-memory, per-conversation serial turns through terminal action-result handling."""
from .boundary import digest
from .records import Ref, Space, json_value
from .runtime import ContractError


class SerialSession:
    def __init__(self, boundary):
        if boundary.session is not None:
            raise ContractError('SessionCoordinatorAlreadyRegistered')
        self.b = boundary
        boundary.session = self
        self.queues = {}
        self.active = {}
        self.turns = {}
        self.scopes = {}
        self.context_turns = {}
        self.input_turns = {}
        self.intent_turns = {}
        self.in_flight = {}
        self.processed_results = set()

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
        self.input_turns[input_ref] = None
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
        self.input_turns[input_ref] = ref
        return ref

    def context_turn(self, context):
        explicit = self.context_turns.get(context.identity)
        if explicit is not None:
            return explicit
        # Known ordinary input cannot escape closure by assembling another Context.
        owners = set()
        for item in context.items:
            if item.record.ref in self.input_turns:
                owner = self.input_turns[item.record.ref]
                if owner is None:
                    raise ContractError('QueuedInputInActiveContext')
                owners.add(owner)
        if len(owners) > 1:
            raise ContractError('MixedTurnContext')
        if owners:
            owner = next(iter(owners))
            self.context_turns[context.identity] = owner
            return owner
        return None

    def check_open(self, turn):
        t = self.turns[turn]
        if t['phase'] in ('CLOSING', 'SETTLED') or self.active.get(t['conversation']) != turn:
            raise ContractError('TurnClosed')

    def check_context_open(self, context):
        turn = self.context_turn(context)
        if turn is not None:
            self.check_open(turn)

    def bind_reasoning_context(self, turn, context):
        t = self.require(turn, 'INPUT')
        if self.b._contexts.get(context.identity) != context:
            raise ContractError('RegisteredContextRequired')
        if (context.subject, context.scope, context.purpose) != (t['subject'], t['scope'], t['purpose']):
            raise ContractError('TurnContextInputMismatch')
        owner = self.context_turn(context)
        if owner is not None and owner != turn:
            raise ContractError('TurnContextInputMismatch')
        # Observation may bind the exact work fact rather than its interaction envelope.
        self.context_turns[context.identity] = turn
        self._event('TurnReasoningContextBound', turn, context_id=context.identity)

    def policy_turn(self, policy_ref):
        # Use actual registered candidate/commit provenance, never model-authored metadata.
        for candidate in self.b._candidates.values():
            if candidate.record.ref == policy_ref and self.b.h.get(policy_ref) is not None:
                record = self.b.h.get(policy_ref)
                if 'candidate-sha256:' + digest(candidate) in record.provenance:
                    return self.context_turn(self.b._contexts[candidate.context_id])
        return None

    def check_policy_open(self, policy_ref):
        turn = self.policy_turn(policy_ref)
        if turn is not None:
            self.check_open(turn)
        return turn

    def register_intent(self, policy_ref, intent_ref):
        turn = self.check_policy_open(policy_ref)
        if turn is not None:
            self.intent_turns[intent_ref] = turn

    def before_effect(self, intent_ref):
        turn = self.intent_turns.get(intent_ref)
        if turn is not None:
            self.check_open(turn)
            if intent_ref in self.in_flight:
                raise ContractError('EffectAlreadyInFlight')
            self.in_flight[intent_ref] = self._event('EffectDispatchStarted', turn, intent_ref=json_value(intent_ref))

    def executor_returned(self, intent_ref, result_ref):
        # Only synchronous mock executors call this hook. A timeout in a real executor
        # must not fabricate this quiescence evidence.
        turn = self.intent_turns.get(intent_ref)
        if turn is not None:
            result = self.b.h.get(result_ref)
            if (result is None or result.kind != 'ActionExecutionResult'
                    or result.payload['intent_ref'] != json_value(intent_ref)):
                raise ContractError('TurnActionResultBindingMismatch')
            dispatched = self.in_flight.pop(intent_ref, None)
            self._event('EffectExecutorReturned', turn, result_ref=json_value(result_ref),
                        dispatch_ref=json_value(dispatched) if dispatched else None,
                        quiescence_basis='SYNCHRONOUS-MOCK-RETURN')

    def begin_close(self, turn, failure_ref):
        self.check_open(turn)
        t = self.turns[turn]
        failure = self.b.h.get(failure_ref)
        if failure is None or failure_ref.space not in (Space.EXECUTION, Space.AUDIT) or failure.subject != t['subject']:
            raise ContractError('TurnFailureReferenceRequired')
        p = failure.payload
        matches = p.get('turn_ref') == json_value(turn)
        if p.get('context_id') in self.b._contexts:
            matches = matches or self.context_turn(self.b._contexts[p['context_id']]) == turn
        if p.get('candidate_digest'):
            matches = matches or any(digest(c) == p['candidate_digest'] and
                self.context_turn(self.b._contexts[c.context_id]) == turn for c in self.b._candidates.values())
        if not matches or failure.kind not in ('TurnFailure', 'LLMGenerationFailed', 'LLMValidationFailed',
                'ResponsibilityClassificationFailed', 'ArithmeticExtractionFailed', 'CommitOutcome'):
            raise ContractError('TurnFailureReferenceRequired')
        if failure.kind == 'CommitOutcome' and p.get('status') == 'Committed':
            raise ContractError('SuccessfulCommitIsNotFailure')
        t.update(phase='CLOSING', failure_ref=failure_ref)
        return self._event('TurnClosing', turn, failure_ref=json_value(failure_ref), termination_reason='FAILED')

    def finish_close(self, turn):
        t = self.require(turn, 'CLOSING')
        owned = [ref for ref, owner in self.intent_turns.items() if owner == turn]
        if any(ref in self.in_flight for ref in owned):
            raise ContractError('EffectQuiescenceNotConfirmed')
        for intent in owned:
            result = next((r for r in self.b.h.executions.records(t['subject']) if r.kind == 'ActionExecutionResult'
                           and r.payload['intent_ref'] == json_value(intent)), None)
            if result is None:
                # An admitted intent that was never dispatched is factual NotOccurred.
                result_ref = self.b.execution('ActionExecutionResult', t['subject'], {
                    'intent_ref':json_value(intent), 'status':'NotOccurred',
                    'reason':'TurnClosedBeforeDispatch', 'occurrence_ref':None})
                result = self.b.h.get(result_ref)
            if result.ref not in self.processed_results:
                self._event('ActionResultProcessed', turn, result_ref=json_value(result.ref),
                            status=result.payload['status'], closing=True)
                self.processed_results.add(result.ref)
        self._event('TurnSettled', turn, conversation=t['conversation'], termination_reason='FAILED',
                    failure_ref=json_value(t['failure_ref']))
        t.update(phase='SETTLED', termination_reason='FAILED')
        del self.active[t['conversation']]

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
        self.bind_reasoning_context(turn, context)
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
        if outcome.status != 'Committed':
            self.begin_close(turn, outcome.audit_ref)

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
        self.processed_results.add(result_ref)
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
        if self.turns.get(turn, {}).get('phase') == 'CLOSING':
            return self.finish_close(turn)
        t = self.require(turn, 'READY')
        if any(owner == turn and ref in self.in_flight for ref, owner in self.intent_turns.items()):
            raise ContractError('EffectQuiescenceNotConfirmed')
        self._event('TurnSettled', turn, conversation=t['conversation'])
        t['phase'] = 'SETTLED'
        del self.active[t['conversation']]
