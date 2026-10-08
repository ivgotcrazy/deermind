"""Explicit observer positions and exact bounded arithmetic on model-selected tokens.

No candidate text is parsed or semantically classified here. The LLM maps text
to expressions and positions; mandatory semantic review checks that mapping.
"""
from .arithmetic import number
from .candidate_spans import registry, partition, span
from .expressions import SPEAKERS
from .runtime import ContractError
from .structured_output import matches_schema

FORMAT = 'observer-arithmetic-v1'
POSITIONS = ('AFFIRMS_TRUE', 'ASSERTS_FALSE', 'REPORTS_ONLY', 'NO_TRUTH_CLAIM', 'UNRESOLVED')


def contract():
    def string(values=None):
        return {'type': 'string', **({'enum': list(values)} if values else {})}
    def obj(properties):
        return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}
    variants = []
    for kind in ('ArithmeticEquality', 'ScalarValue', 'UnevaluatedExpression', 'UnresolvedNumericMapping'):
        positions = POSITIONS[:3] if kind in ('ArithmeticEquality', 'ScalarValue') else (
            ('REPORTS_ONLY', 'NO_TRUTH_CLAIM') if kind == 'UnevaluatedExpression' else POSITIONS)
        variants.append(obj({'type': string((kind,)), 'span_ids': {'type': 'array', 'items': string()},
            'speaker': string(SPEAKERS), 'sources': {'type': 'array', 'items': string()},
            'observer_position': string(positions),
            'expression_tokens': {'type': 'array', 'items': string()},
            'value': string() if kind in ('ArithmeticEquality', 'ScalarValue') else {'type': 'null'},
            'reason': string()}))
    segment = obj({'span_ids': {'type': 'array', 'items': string()},
        'coverage': string(('COMPLETE', 'UNRESOLVED')), 'expressions': {'type': 'array', 'items': {'anyOf': variants}}})
    return {'name': 'submit_extraction', 'parameters': obj({'segments': {'type': 'array', 'items': segment}})}


def evaluate(tokens):
    """Infix grammar over typed tokens, not natural language; never eval().

    Return None for a well-formed undefined division. Negative decimals are one
    number token. Parentheses and operator precedence preserve the mapped expression.
    """
    if not isinstance(tokens, list) or not 1 <= len(tokens) <= 64 or any(not isinstance(t, str) for t in tokens):
        raise ContractError('InvalidArithmeticTokenList')
    cursor = 0
    def factor(depth):
        nonlocal cursor
        if depth > 16 or cursor >= len(tokens):
            raise ContractError('InvalidArithmeticTokenGrammar')
        token = tokens[cursor]
        cursor += 1
        if token == '(':
            value = expression(depth + 1)
            if cursor >= len(tokens) or tokens[cursor] != ')':
                raise ContractError('InvalidArithmeticTokenGrammar')
            cursor += 1
            return value
        return number(token)
    def term(depth):
        nonlocal cursor
        value = factor(depth)
        while cursor < len(tokens) and tokens[cursor] in ('*', '/'):
            op = tokens[cursor]
            cursor += 1
            other = factor(depth)
            value = None if value is None or other is None or (op == '/' and other == 0) else (
                value * other if op == '*' else value / other)
        return value
    def expression(depth):
        nonlocal cursor
        value = term(depth)
        while cursor < len(tokens) and tokens[cursor] in ('+', '-'):
            op = tokens[cursor]
            cursor += 1
            other = term(depth)
            value = None if value is None or other is None else (value + other if op == '+' else value - other)
        return value
    result = expression(0)
    if cursor != len(tokens):
        raise ContractError('InvalidArithmeticTokenGrammar')
    return result


def check(output, candidate, sources):
    if not matches_schema(output, contract()['parameters']):
        raise ContractError('InvalidObserverArithmeticShape')
    entries, lookup = registry(candidate), {s['handle']: s for s in sources}
    checks, statuses = [], []
    for index, (segment, container) in enumerate(partition(output['segments'], candidate, entries)):
        if segment['coverage'] == 'UNRESOLVED':
            statuses.append('UNRESOLVED')
        if len(segment['expressions']) > 64:
            raise ContractError('TooManyIndexedExpressions')
        for position, item in enumerate(segment['expressions']):
            bound = span(item['span_ids'], entries)
            if (bound['field'] != container['field'] or bound['start'] < container['start']
                    or bound['end'] > container['end']):
                raise ContractError('ExpressionOutsideIndexedSegment')
            refs, kind = item['sources'], item['type']
            if len(refs) != len(set(refs)) or any(r not in lookup for r in refs):
                raise ContractError('InvalidExpressionSourceHandle')
            if kind != 'UnresolvedNumericMapping' and not refs:
                raise ContractError('ExpressionSourceRequired')
            computed, relation, status = None, None, 'NOT_APPLICABLE'
            tokens, viewpoint = item['expression_tokens'], item['observer_position']
            if kind == 'ArithmeticEquality':
                value = number(item['value'])
                computed = evaluate(tokens)
                relation = computed == value if computed is not None else None
                if viewpoint == 'REPORTS_ONLY':
                    status = 'PASS'  # Mapping fidelity and source support are still required.
                elif relation is None:
                    status = 'UNRESOLVED'
                else:
                    status = 'PASS' if relation == (viewpoint == 'AFFIRMS_TRUE') else 'FAIL'
            elif kind == 'ScalarValue':
                if tokens:
                    raise ContractError('ScalarCannotCarryEquation')
                number(item['value'])
            elif kind == 'UnevaluatedExpression':
                evaluate(tokens)  # Validate grammar only; do not publish a missing result.
            else:
                if tokens or not item['reason'].strip():
                    raise ContractError('UnresolvedMappingRequiresReasonAndEmptyTokens')
                status = 'UNRESOLVED'
            if item['speaker'] == 'unresolved' or viewpoint == 'UNRESOLVED':
                status = 'UNRESOLVED'
            statuses.append(status)
            checks.append({'segment': index, 'expression': position, **bound, **item,
                'bound_sources': [lookup[r] for r in refs],
                'computed': str(computed) if computed is not None else None,
                'relation_holds': relation, 'status': status})
    overall = 'FAIL' if 'FAIL' in statuses else 'UNRESOLVED' if 'UNRESOLVED' in statuses else 'PASS'
    return {'format': FORMAT, 'status': overall, 'mapping_required': True, 'checks': checks}
