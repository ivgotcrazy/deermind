"""Audit projection of actual checks; no semantic classification or admission authority."""
FORMAT = 'validation-dimensions-v1'
GROUPS = {'content_validity':['grounding','boundary','arithmetic_mapping','attribution'],
          'required_meaning':['method','division','final_result']}
STAGES = ('responsibility','arithmetic','semantic_review')


def check_dimensions(definition):
    profile=definition.get('validation_dimensions')
    if profile != {'format':FORMAT,'criteria_groups':GROUPS}:
        raise ValueError('UnsupportedValidationDimensions')
    if (set(c['id'] for c in definition['criteria']) != set(sum(GROUPS.values(),[]))
            or definition.get('responsibility_profile') != 'separate-classification-v1'
            or definition.get('arithmetic_extraction_format') not in ('typed-expressions-v1','typed-expressions-v2','observer-arithmetic-v1')):
        raise ValueError('RequiredDimensionChecksMissing')


def combine(states):
    return 'FAIL' if 'FAIL' in states else 'UNRESOLVED' if 'UNRESOLVED' in states else 'PASS'


def execution_summary(states):
    if 'FAILED' in states:return 'FAILED'
    if all(s=='COMPLETED' for s in states):return 'COMPLETED'
    return 'NOT_RUN' if all(s=='NOT_RUN' for s in states) else 'INCOMPLETE'


def assessment(definition, stages, criteria, *, review_status=None, recheck_failures=()):
    """Inputs come from validated execution records, not raw provider output."""
    check_dimensions(definition)
    rows=[]
    for stage in STAGES[:2]:
        rows.append({'id':stage,'dimension':'content_validity','required':True,**stages[stage]})
    semantic=stages['semantic_review']
    for dimension,identities in GROUPS.items():
        for identity in identities:
            rows.append({'id':identity,'dimension':dimension,'required':True,
                'execution_status':semantic['execution_status'],
                'conclusion':criteria[identity] if semantic['execution_status']=='COMPLETED' else None,
                'source_ref':semantic['source_ref']})
    dimensions={}
    for dimension in GROUPS:
        checks=[r for r in rows if r['dimension']==dimension]
        executions=[r['execution_status'] for r in checks]
        complete=all(s=='COMPLETED' for s in executions)
        dimensions[dimension]={'execution_status':execution_summary(executions),
            'conclusion':combine([r['conclusion'] for r in checks]) if complete else None}
    execution='FAILED' if recheck_failures else execution_summary([s['execution_status'] for s in stages.values()])
    return {'format':FORMAT,'execution_status':execution,'checks':rows,'dimensions':dimensions,
        'review_status':review_status,'recheck_failure_refs':list(recheck_failures),
        'all_required_checks_passed':execution=='COMPLETED' and review_status=='PASS'
            and all(r['execution_status']=='COMPLETED' and r['conclusion']=='PASS' for r in rows),
        'audit_only':True}
