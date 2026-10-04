"""Open LLM Policy with exact mechanical admission and separate test-only review."""
import json

from .boundary import digest
from .records import Space, json_value
from .runtime import ContractError
from .security import DataUse, Operation
from .structured_output import matches_schema


def policy_legality(payload, context):
    """Typed constraints only: never interpret requests, rationale, or teaching value."""
    records = {json.dumps(json_value(i.record.ref), sort_keys=True): i.record for i in context.items}
    refs = payload.get('context_refs')
    if not isinstance(refs, list) or not refs or any(json.dumps(r, sort_keys=True) not in records for r in refs):
        return 'PolicyContextReferenceInvalid'
    envelopes = [i.record.payload for i in context.items if i.record.kind == 'ActivityConstraints']
    if len(envelopes) != 1 or payload.get('episode') != envelopes[0]['episode']:
        return 'PolicyActivityBindingInvalid'
    outcome = payload.get('outcome')
    action_fields = ('action_identity', 'action_revision', 'exact_payload', 'executor_target')
    if outcome in ('NoIntervention', 'Defer'):
        if any(payload.get(k) != '' for k in action_fields):
            return 'NonExecuteCarriesAction'
        if (outcome == 'Defer') != bool(payload.get('defer_condition', '').strip()):
            return 'DeferConditionShapeInvalid'
        return ''
    if outcome != 'Execute' or payload.get('defer_condition') != '':
        return 'PolicyOutcomeShapeInvalid'
    selected = {'space': 'canonical', 'identity': payload.get('action_identity'), 'revision': payload.get('action_revision')}
    if selected not in envelopes[0]['allowed_action_refs']:
        return 'ActionOutsideActivityEnvelope'
    action = records.get(json.dumps(selected, sort_keys=True))
    if action is None or action.kind != 'ActionSemantic':
        return 'ActionSemanticMissingFromContext'
    if any(payload.get(k) != action.payload[k] for k in ('exact_payload', 'executor_target')):
        return 'ExactActionParametersMismatch'
    return ''


class PolicyRuntime:
    def __init__(self, boundary, definition, review_ref):
        self.runtime, self.definition, self.review_ref = boundary, definition, review_ref

    def utility_review(self, token, candidate, adapter):
        """Measurement only. Never returns a commit validation or changes a candidate."""
        b = self.runtime
        if b._candidates.get(candidate.identity) != candidate:
            raise ContractError('UnregisteredOrAlteredCandidate')
        context = b._contexts[candidate.context_id]
        if adapter.config.base_url != b._protocols[context.protocol].destination:
            raise ContractError('ModelDestinationMismatch')
        source = b.execution('PolicyUtilityReviewStarted', context.subject,
            {'candidate_digest': digest(candidate), 'context_id': context.identity, 'rule_ref': json_value(self.review_ref)})
        b.security.enforce(token, Operation(context.purpose, context.subject, self.review_ref.identity, 'review_for_test'), source,
            DataUse(context.purpose, context.subject, 'PolicyOutcome', 'review_for_test', adapter.config.base_url))
        rule, _ = b.security.read(token, self.review_ref, context.purpose, adapter.config.base_url, source, ('PolicyUtilityRules',))
        content = b._model_context(token, context, source)
        output, call_id = adapter.complete([
            {'role': 'system', 'content': rule.payload['system']},
            {'role': 'user', 'content': json.dumps({'context': content, 'candidate': candidate.record.payload,
                'rubric': rule.payload['rubric']}, ensure_ascii=False)}], 'PolicyUtilityReview',
            output_contract=self.definition['output_contracts']['utility'])
        if not matches_schema(output, self.definition['output_contracts']['utility']['parameters']):
            raise ContractError('PolicyUtilitySchemaMismatch')
        scores = output['scores']
        if len(scores) != 4 or {s['id'] for s in scores} != set(rule.payload['rubric']):
            raise ContractError('PolicyUtilityRubricIncomplete')
        status = 'FAIL' if any(s['status'] == 'FAIL' for s in scores) else 'UNRESOLVED' if any(s['status'] == 'UNRESOLVED' for s in scores) else 'PASS'
        ref = b.execution('PolicyUtilityReview', context.subject, {'candidate_digest': digest(candidate),
            'context_id': context.identity, 'rule_ref': json_value(self.review_ref), 'model_ref': adapter.config.model,
            'model_call': call_id, 'status': status, 'output': output, 'test_only': True})
        return ref
