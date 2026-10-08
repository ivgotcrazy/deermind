"""Typed LLM mappings, exact span/source binding and arithmetic; no text classification."""
from fractions import Fraction

from .arithmetic import check_arithmetic_extraction, number
from .runtime import ContractError


FORMAT = 'typed-expressions-v1'
TYPES = ('NumericAssertion', 'UnevaluatedExpression', 'UnresolvedNumericMapping')
OPERATORS = ('add', 'subtract', 'multiply', 'divide')
STANCES = ('asserted_true', 'asserted_false', 'reported_only', 'not_asserted', 'unresolved')
SPEAKERS = ('system', 'learner', 'other', 'unresolved')


def extraction_contract(fields):
    def string(choices=None):
        return {'type':'string', **({'enum':list(choices)} if choices is not None else {})}
    def obj(properties):
        return {'type':'object', 'properties':properties, 'required':list(properties), 'additionalProperties':False}
    def nullable(schema):
        return {'anyOf':[schema, {'type':'null'}]}
    expression = obj({'type':string(TYPES), 'text':string(), 'speaker':string(SPEAKERS),
        'sources':{'type':'array', 'items':string()}, 'stance':string(STANCES),
        'operator':nullable(string(OPERATORS)), 'left':nullable(string()), 'right':nullable(string()),
        'value':nullable(string()), 'reason':string()})
    segment = obj({'field':string(fields), 'text':string(), 'coverage':string(('COMPLETE','UNRESOLVED')),
                   'expressions':{'type':'array', 'items':expression}})
    return {'name':'submit_extraction', 'parameters':obj({'segments':{'type':'array', 'items':segment}})}


def check_expression_extraction(output, candidate, registry):
    if not isinstance(output, dict) or set(output) != {'segments'}:
        raise ContractError('InvalidExpressionExtractionShape')
    segments = output['segments']
    if not isinstance(segments, list) or not 1 <= len(segments) <= 32:
        raise ContractError('InvalidExpressionSegments')
    cursors, checks, statuses = {f:0 for f in candidate}, [], []
    sources = {r['handle']:r for r in registry}
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict) or set(segment) != {'field','text','coverage','expressions'}:
            raise ContractError('InvalidExpressionSegmentShape')
        field, text = segment['field'], segment['text']
        if (not isinstance(field,str) or field not in candidate or not isinstance(candidate[field],str)
                or not isinstance(text,str) or not text.strip()):
            raise ContractError('InvalidExpressionFieldOrSpan')
        start = candidate[field].find(text, cursors[field])
        if start < 0 or candidate[field][cursors[field]:start].strip():
            raise ContractError('ExpressionCoverageGap')
        cursors[field] = start + len(text)
        if segment['coverage'] not in ('COMPLETE','UNRESOLVED'):
            raise ContractError('InvalidExpressionCoverage')
        if segment['coverage'] == 'UNRESOLVED':statuses.append('UNRESOLVED')
        items = segment['expressions']
        if not isinstance(items,list) or len(items) > 16:
            raise ContractError('InvalidExpressionItems')
        for position, item in enumerate(items):
            if not isinstance(item,dict) or set(item) != {'type','text','speaker','sources','stance','operator','left','right','value','reason'}:
                raise ContractError('InvalidExpressionShape')
            kind, quote = item['type'], item['text']
            if kind not in TYPES or not isinstance(quote,str) or not quote.strip() or text.count(quote) != 1:
                raise ContractError('InvalidOrAmbiguousExpressionSpan')
            if item['speaker'] not in SPEAKERS or item['stance'] not in STANCES or not isinstance(item['reason'],str):
                raise ContractError('InvalidExpressionAttribution')
            refs = item['sources']
            if (not isinstance(refs,list) or any(not isinstance(r,str) or r not in sources for r in refs)
                    or len(refs) != len(set(refs))):
                raise ContractError('InvalidExpressionSourceHandle')
            if kind != 'UnresolvedNumericMapping' and not refs:
                raise ContractError('ExpressionSourceRequired')
            computed, relation, status = None, None, 'NOT_APPLICABLE'
            if kind == 'NumericAssertion':
                assertion = {k:item[k] for k in ('operator','left','right','value','stance')}
                result = check_arithmetic_extraction({'segments':[{'field':field,'text':quote,'coverage':'COMPLETE',
                    'assertions':[assertion]}]}, {field:quote})
                numeric = result['checks'][0]
                computed, status = numeric['computed'], numeric['status']
                if computed is not None:
                    relation = Fraction(computed) == Fraction(item['value'])
            elif kind == 'UnevaluatedExpression':
                if item['value'] is not None or item['stance'] not in ('not_asserted','reported_only'):
                    raise ContractError('UnevaluatedExpressionCannotAssertResult')
                if item['operator'] is None:
                    if item['left'] is not None or item['right'] is not None:
                        raise ContractError('UnevaluatedOperandWithoutOperator')
                else:
                    if item['operator'] not in OPERATORS:raise ContractError('InvalidExpressionOperator')
                    for operand in ('left','right'):
                        if item[operand] is not None:number(item[operand])
                # No calculation or substitution for a missing result, even with known operands.
            else:
                if any(item[k] is not None for k in ('operator','left','right','value')) or not item['reason'].strip():
                    raise ContractError('UnresolvedMappingRequiresReasonAndNullNumbers')
                status = 'UNRESOLVED'
            if item['speaker'] == 'unresolved':status = 'UNRESOLVED'
            statuses.append(status)
            offset = start + text.index(quote)
            checks.append({'segment':index, 'expression':position, 'field':field, 'start':offset,
                'end':offset+len(quote), **item, 'bound_sources':[sources[r] for r in refs],
                'computed':computed, 'relation_holds':relation, 'status':status})
    if any(not isinstance(text,str) or text[cursors[field]:].strip() for field,text in candidate.items()):
        raise ContractError('IncompleteExpressionCoverage')
    overall = 'FAIL' if 'FAIL' in statuses else 'UNRESOLVED' if 'UNRESOLVED' in statuses else 'PASS'
    return {'format':FORMAT, 'status':overall, 'mapping_required':True, 'checks':checks}
