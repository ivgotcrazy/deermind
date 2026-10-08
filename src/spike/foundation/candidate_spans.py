"""Lossless candidate locators; punctuation partitions text, never its meaning.

The model groups adjacent handles and assigns every semantic judgment. The host
expands those exact handles; it never repairs a quote or invents a classification.
"""
from copy import deepcopy
import re

from .runtime import ContractError

FORMAT = 'candidate-span-handles-v1'
QUOTE_SELECTIONS = 'ordered-quote-selections-v1'


def registry(candidate):
    entries = []
    for field, text in candidate.items():
        if not isinstance(text, str) or not text.strip():
            raise ContractError('InvalidCandidateForSpanRegistry')
        # Syntactic locator units, not claims/sentences/semantic classifications.
        # Include delimiters and whitespace in the original byte-for-byte order.
        start = 0
        for match in re.finditer(r'[.,;:!?。；：，！？\n]+\s*|$', text):
            end = match.end()
            if end <= start:
                continue
            part = text[start:end]
            if not part.strip():
                if not entries or entries[-1]['field'] != field:
                    continue
                entries[-1]['end'] = end
                entries[-1]['text'] += part
            else:
                entries.append({'handle': f'candidate_{len(entries)}', 'field': field,
                                'start': start, 'end': end, 'text': part})
            start = end
    if len(entries) > 256:
        raise ContractError('TooManyCandidateLocatorUnits')
    return entries


def span(ids, entries):
    lookup = {r['handle']: r for r in entries}
    if (not isinstance(ids, list) or not ids
            or any(not isinstance(h, str) or h not in lookup for h in ids)
            or len(ids) != len(set(ids))):
        raise ContractError('UnknownOrDuplicateCandidateHandle')
    selected = [lookup[h] for h in ids]
    if any(a['field'] != b['field'] or a['end'] != b['start']
           for a, b in zip(selected, selected[1:])):
        raise ContractError('CandidateHandlesNotContiguous')
    return {'field': selected[0]['field'], 'start': selected[0]['start'],
            'end': selected[-1]['end'], 'text': ''.join(r['text'] for r in selected)}


def partition(rows, candidate, entries):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 256:
        raise ContractError('InvalidCandidatePartition')
    cursors, expanded = {f: 0 for f in candidate}, []
    for row in rows:
        if not isinstance(row, dict) or 'span_ids' not in row:
            raise ContractError('CandidateHandlesRequired')
        bound = span(row['span_ids'], entries)
        if bound['start'] != cursors[bound['field']]:
            raise ContractError('CandidateHandleCoverageGapOrOverlap')
        cursors[bound['field']] = bound['end']
        expanded.append((row, bound))
    if any(cursors[f] != len(text) for f, text in candidate.items()):
        raise ContractError('IncompleteCandidateHandleCoverage')
    return expanded


def indexed_contract(template):
    """Versioned template conversion; no model output is repaired by this code."""
    output = deepcopy(template)
    def visit(schema):
        if not isinstance(schema, dict):
            return
        if schema.get('type') == 'object':
            props = schema['properties']
            if 'field' in props and 'text' in props:
                del props['field'], props['text']
                props['span_ids'] = {'type': 'array', 'items': {'type': 'string'}}
                schema['required'] = list(props)
        for value in schema.values():
            if isinstance(value, dict):
                visit(value)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
    visit(output)
    return output


def bind_contract(template, entries, sources=None):
    output = deepcopy(template)
    def visit(schema):
        if not isinstance(schema, dict):
            return
        if schema.get('type') == 'object':
            props = schema['properties']
            for name, options in [('span_ids', entries), ('sources', sources)]:
                if name in props and options is not None:
                    props[name] = {'type': 'array', 'items': {'type': 'string',
                                   'enum': [r['handle'] for r in options]}}
        for value in schema.values():
            if isinstance(value, dict):
                visit(value)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
    visit(output)
    return output


def expand_classification(wire, candidate):
    if not isinstance(wire, dict) or set(wire) != {'segments'}:
        raise ContractError('InvalidIndexedResponsibility')
    rows = []
    for raw, bound in partition(wire['segments'], candidate, registry(candidate)):
        if set(raw) != {'span_ids', 'role', 'rationale'}:
            raise ContractError('InvalidIndexedResponsibilitySegment')
        rows.append({'field': bound['field'], 'text': bound['text'],
                     'role': raw['role'], 'rationale': raw['rationale']})
    return {'segments': rows}


def quote_spans(ids, entries, encoding=None):
    """Select exact source spans; disjoint selections remain separate quotations."""
    if encoding is None:
        return [span(ids, entries)]
    if encoding != QUOTE_SELECTIONS:
        raise ContractError('UnsupportedCriterionQuoteEncoding')
    positions = {r['handle']: i for i, r in enumerate(entries)}
    if (not isinstance(ids, list) or not ids
            or any(not isinstance(h, str) or h not in positions for h in ids)
            or any(positions[a] >= positions[b] for a, b in zip(ids, ids[1:]))):
        raise ContractError('InvalidOrderedQuoteSelection')
    selected = [entries[positions[h]] for h in ids]
    if len({r['field'] for r in selected}) != 1:
        raise ContractError('CrossFieldQuoteSelection')
    groups = [[ids[0]]]
    for previous, current in zip(ids, ids[1:]):
        if positions[current] == positions[previous] + 1:
            groups[-1].append(current)
        else:
            groups.append([current])
    return [span(group, entries) for group in groups]


def expand_review(wire, candidate, quote_encoding=None):
    if not isinstance(wire, dict) or set(wire) != {'reviewed_fields', 'criteria', 'claims'}:
        raise ContractError('InvalidIndexedReview')
    output, entries = deepcopy(wire), registry(candidate)
    rows = partition(output['claims'], candidate, entries)
    for raw, bound in rows:
        if 'field' in raw or 'text' in raw:
            raise ContractError('UnexpectedIndexedClaimText')
        raw.pop('span_ids')
        raw.update(field=bound['field'], text=bound['text'])
    if not isinstance(output['criteria'], list):
        raise ContractError('InvalidIndexedCriteria')
    for criterion in output['criteria']:
        if not isinstance(criterion, dict) or not isinstance(criterion.get('quotes'), list):
            raise ContractError('InvalidIndexedCriterion')
        quotes = []
        for quote in criterion['quotes']:
            if not isinstance(quote, dict) or set(quote) != {'span_ids'}:
                raise ContractError('InvalidIndexedQuote')
            for bound in quote_spans(quote['span_ids'], entries, quote_encoding):
                quotes.append({'field': bound['field'], 'text': bound['text']})
        criterion['quotes'] = quotes
    return output
