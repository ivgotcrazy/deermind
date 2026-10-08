"""Declared review consistency only. No natural-language classification."""
import json
from .runtime import ContractError
from .structured_output import matches_schema

FORMAT='policy-disposition-v1'
RULES=('S1','S2','S3','S4','S5')
RELATIONS=('SUPPORTED','CONTRADICTED','REQUIRED_BASIS_ABSENT','UNDETERMINED')
REASONS={'PASS':'SATISFIED','FAIL':'CONTENT_DEFECT','UNRESOLVED':'INSUFFICIENT_REVIEW'}

def obj(properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
def array(items):return {'type':'array','items':items}
def string(*choices):return {'type':'string',**({'enum':list(choices)} if choices else {})}
def ref_schema():return obj({'space':string('canonical','fact','derived','execution','audit'),'identity':string(),'revision':string()})
def contract(fields):
    quote=obj({'field':string(*fields),'start':string(),'end':string(),'quote':string()})
    source=obj({'ref':ref_schema(),'field':string(),'start':string(),'end':string(),'quote':string()})
    finding=obj({'id':string(),'rules':array(string(*RULES)),'relation':string(*RELATIONS),
        'candidate_quotes':array(quote),'source_quotes':array(source),'gap_ids':array(string()),'rationale':string()})
    check=obj({'id':string(*RULES),'status':string('PASS','FAIL','UNRESOLVED'),
        'reason_code':string(*REASONS.values()),'finding_ids':array(string()),'rationale':string()})
    gap=obj({'id':string(),'rules':array(string(*RULES)),'material_id':string(),'rationale':string()})
    return {'name':'submit_review','parameters':obj({'candidate_digest':string(),'context_id':string(),
        'rule_ref':ref_schema(),'material_record_ref':ref_schema(),'reviewed_fields':array(string(*fields)),
        'checks':array(check),'findings':array(finding),'review_material_gaps':array(gap),
        'status':string('PASS','FAIL','UNRESOLVED'),'rationale':string()})}

def combine(values):return 'FAIL' if 'FAIL' in values else 'UNRESOLVED' if 'UNRESOLVED' in values else 'PASS'
def require(condition,reason):
    if not condition:raise ContractError(reason)
def unique(values,reason):
    require(len(values)==len(set(values)),reason)
def quote(text,q):
    require(isinstance(text,str),'DispositionQuoteFieldInvalid')
    # Offsets are decimal strings because the current strict-schema subset supports strings.
    require(all(isinstance(q[k],str) and q[k] and q[k].isascii() and q[k].isdecimal() for k in ('start','end')),'DispositionOffsetInvalid')
    start,end=int(q['start']),int(q['end'])
    require(0<=start<end<=len(text) and text[start:end]==q['quote'],'DispositionQuoteMismatch')
def check(output,payload,content,binding,materials):
    fields=list(payload)
    require(matches_schema(output,contract(fields)['parameters']),'DispositionSchemaMismatch')
    for key,value in binding.items():require(output[key]==value,'DispositionBindingMismatch')
    require(output['rationale'].strip()!='','DispositionRationaleMissing')
    unique(output['reviewed_fields'],'DispositionFieldCoverage')
    require(set(output['reviewed_fields'])==set(fields),'DispositionFieldCoverage')
    checks={r['id']:r for r in output['checks']}
    require(len(checks)==len(output['checks'])==5 and set(checks)==set(RULES),'DispositionRuleCoverage')
    available={r['id']:r for r in materials}
    gaps={r['id']:r for r in output['review_material_gaps']}
    findings={r['id']:r for r in output['findings']}
    require(len(gaps)==len(output['review_material_gaps']) and len(findings)==len(output['findings']),'DispositionDuplicateEvidence')
    sources={json.dumps(r['ref'],sort_keys=True):r['content'] for r in content}
    for g in gaps.values():
        require(g['id'] and g['rationale'].strip() and g['rules'],'DispositionGapInvalid')
        unique(g['rules'],'DispositionDuplicateRule')
        material=available.get(g['material_id'])
        require(material is not None and material['state']!='AVAILABLE','DispositionUntrustedMaterialGap')
    used_gaps=set()
    expected={r:[] for r in RULES}
    for f in findings.values():
        require(f['id'] and f['rules'] and f['rationale'].strip() and f['candidate_quotes'],'DispositionFindingInvalid')
        unique(f['rules'],'DispositionDuplicateRule');unique(f['gap_ids'],'DispositionDuplicateGap')
        for q in f['candidate_quotes']:quote(payload[q['field']],q)
        for q in f['source_quotes']:
            source=sources.get(json.dumps(q['ref'],sort_keys=True))
            require(source is not None and q['field'] in source,'DispositionSourceOutsideContext')
            quote(source[q['field']],q)
        for gid in f['gap_ids']:
            require(gid in gaps and set(f['rules'])<=set(gaps[gid]['rules']),'DispositionGapBindingMismatch');used_gaps.add(gid)
        require(f['relation']=='UNDETERMINED' or not f['gap_ids'],'DispositionResolvedFindingHasGap')
        require(f['source_quotes'] or f['relation'] in ('CONTRADICTED','REQUIRED_BASIS_ABSENT','UNDETERMINED'),'DispositionSupportSourceMissing')
        status={'SUPPORTED':'PASS','CONTRADICTED':'FAIL','REQUIRED_BASIS_ABSENT':'FAIL','UNDETERMINED':'UNRESOLVED'}[f['relation']]
        for rule in f['rules']:
            require(f['id'] in checks[rule]['finding_ids'],'DispositionFindingNotAccounted');expected[rule].append(status)
    require(used_gaps==set(gaps),'DispositionGapNotAccounted')
    for rule,c in checks.items():
        unique(c['finding_ids'],'DispositionDuplicateFinding')
        require(c['rationale'].strip() and c['finding_ids'],'DispositionEvidenceMissing')
        for fid in c['finding_ids']:require(fid in findings and rule in findings[fid]['rules'],'DispositionFindingRuleMismatch')
        require(c['status']==combine(expected[rule]) and c['reason_code']==REASONS[c['status']],'DispositionCheckContradiction')
    require(output['status']==combine([c['status'] for c in checks.values()]),'DispositionOverallContradiction')
    return output['status'],output['rationale']
