"""Host-resolved full-field evidence. Model supplies locators, never quotations."""
from copy import deepcopy

from .policy_disposition import contract as offset_contract, obj, array, string, require
from .policy_field_quotes import registry as quote_registry

FORMAT = 'policy-disposition-fields-v3'


def registry(payload, content):
    # Keep the old locator numbering, but never offer an empty field as prose evidence.
    return {side:[row for row in rows if row['text']]
            for side,rows in quote_registry(payload, content).items()}


def contract(fields, entries=None):
    result = offset_contract(fields)
    finding = result['parameters']['properties']['findings']['items']['properties']
    for side,key in (('candidate','candidate_quotes'),('source','source_quotes')):
        choices = None if entries is None else [row['handle'] for row in entries[side]]
        handle = string() if choices is None else string(*(choices or ['NO_NONEMPTY_STRING_FIELD']))
        finding[key] = array(obj({'handle':handle}))
    return result


def expand(output, entries):
    result = deepcopy(output)
    for finding in result['findings']:
        for side,key in (('candidate','candidate_quotes'),('source','source_quotes')):
            lookup = {row['handle']:row for row in entries[side]}
            expanded = []
            for reference in finding[key]:
                require(isinstance(reference,dict) and set(reference)=={'handle'},
                        'DispositionFieldReferenceShape')
                require(isinstance(reference['handle'],str) and reference['handle'] in lookup,
                        'DispositionUnknownFieldReference')
                row = lookup[reference['handle']]
                text = row['text']
                require(isinstance(text,str) and bool(text), 'DispositionEmptyReferencedField')
                expanded.append({'field':row['field'],'start':'0','end':str(len(text)), 'quote':text,
                    **({'ref':deepcopy(row['ref'])} if side=='source' else {})})
            finding[key] = expanded
    return result
