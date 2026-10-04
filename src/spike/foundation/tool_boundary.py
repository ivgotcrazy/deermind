"""Exact tool requests are untrusted data; only installed backend grants authorize them."""
from .boundary import digest
from .llm import strict_json
from .records import json_value
from .runtime import ContractError
from .security import AccessDenied, DataUse, Operation, parameter
from .structured_output import matches_schema


class ToolBoundary:
    def __init__(self, runtime, schema, resources, handlers):
        self.runtime, self.security, self.h = runtime, runtime.security, runtime.h
        # Trusted server mappings, never resolved from model-provided module/function names.
        self.schema, self.resources, self.handlers = schema, dict(resources), dict(handlers)

    def dispatch(self, token, candidate):
        if self.runtime._candidates.get(candidate.identity) != candidate:
            raise ContractError('UnregisteredOrAlteredCandidate')
        context = self.runtime._contexts[candidate.context_id]
        payload = candidate.record.payload
        if not matches_schema(payload, self.schema):
            raise ContractError('MalformedToolRequest')
        source = self.runtime.execution('ToolBoundaryAttempt', context.subject,
            {'candidate_digest': digest(candidate), 'candidate_execution': json_value(candidate.execution),
             'context_id': context.identity, 'request': payload})
        if payload['decision'] == 'REFUSE':
            return {'status': 'MODEL_REFUSED', 'source': json_value(source)}
        raw = payload['request']
        try:
            params = tuple(parameter(p['name'], strict_json(p['value'])) for p in raw['parameters'])
        except (ValueError, TypeError):
            raise ContractError('MalformedToolParameters') from None
        request = Operation(raw['purpose'], raw['subject'], raw['resource'], raw['operation'], params)
        try:
            self.security.enforce(token, request, source, expected_principal=context.principal)
            if raw['operation'] == 'read':
                ref = self.resources.get(raw['resource'])
                if ref is None:
                    raise ContractError('MissingExactResourceMapping')
                record = self.h.get(ref)
                # Actual stored subject/type determine data access, not the caller's claims.
                use = DataUse(raw['purpose'], record.subject, record.kind, 'read', raw['destination'],
                              raw['retention'], raw['disclosure'])
                actual = Operation(raw['purpose'], record.subject, record.ref.identity, 'read', params)
                self.security.enforce(token, actual, source, use, expected_principal=context.principal)
                record, _ = self.security.read(token, ref, raw['purpose'], raw['destination'], source)
                result = {'status': 'ALLOWED', 'read_ref': json_value(record.ref)}
            else:
                if raw['operation'] not in self.handlers:
                    raise ContractError('UnsupportedToolOperation')
                result = self.handlers[raw['operation']](source, request)
            return {**result, 'source': json_value(source)}
        except AccessDenied as exc:
            return {'status': 'DENIED', 'reason': exc.decision.reason, 'category': exc.category,
                    'source': json_value(source)}
