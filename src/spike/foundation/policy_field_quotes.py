"""Exact unique quotes in runtime-enumerated string fields. No semantic heuristics."""
from copy import deepcopy
from .policy_disposition import contract as offset_contract, obj, array, string, require
from .source_handles import source_registry

FORMAT='policy-disposition-fields-v2'

def registry(payload,content):
    candidates=[{'handle':'candidate_'+str(n),'field':name,'text':text} for n,(name,text) in enumerate(sorted(payload.items())) if isinstance(text,str)]
    # source_registry's existing ordering/shape is shared; it rejects empty registries.
    sources=source_registry(content) if any(isinstance(v,str) for r in content for v in r['content'].values()) else []
    return {'candidate':candidates,'source':sources}

def contract(fields,entries=None):
    result=offset_contract(fields)
    finding=result['parameters']['properties']['findings']['items']['properties']
    for side,key in (('candidate','candidate_quotes'),('source','source_quotes')):
        choices=None if entries is None else [r['handle'] for r in entries[side]]
        handle=string() if choices is None else string(*(choices or ['NO_VISIBLE_STRING_FIELD']))
        finding[key]=array(obj({'handle':handle,'quote':string()}))
    return result

def expand(output,entries):
    result=deepcopy(output)
    for finding in result['findings']:
        for side,key in (('candidate','candidate_quotes'),('source','source_quotes')):
            lookup={r['handle']:r for r in entries[side]};expanded=[]
            for q in finding[key]:
                require(set(q)=={'handle','quote'} and q['handle'] in lookup,'DispositionUnknownFieldHandle')
                item=lookup[q['handle']];text=item['text'];part=q['quote']
                require(isinstance(part,str) and bool(part),'DispositionEmptyFieldQuote')
                start=text.find(part)
                require(start>=0,'DispositionFieldQuoteNotFound')
                # Include overlapping repeats, not just disjoint str.count matches.
                require(text.find(part,start+1)<0,'DispositionFieldQuoteAmbiguous')
                expanded.append({'field':item['field'],'start':str(start),'end':str(start+len(part)),'quote':part,
                    **({'ref':deepcopy(item['ref'])} if side=='source' else {})})
            finding[key]=expanded
    return result
