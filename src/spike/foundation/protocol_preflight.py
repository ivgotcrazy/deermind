"""Check declared mechanical contracts before a bounded model campaign."""
from .structured_output import check_schema
from .expressions import FORMAT, FORMAT_V2, extraction_contract, extraction_contract_v2
from .observer_arithmetic import FORMAT as OBSERVER_FORMAT, contract as observer_contract
from .candidate_spans import FORMAT as SPAN_FORMAT, QUOTE_SELECTIONS
from .validation_dimensions import check_dimensions


def check_observation_contract(definition):
    contracts=definition['output_contracts']
    for contract in contracts.values():
        check_schema(contract['parameters'])
    schema=contracts['generation']['parameters']
    if set(schema['properties'])!={'description'} or schema['properties']['description']['type']!='string':
        raise ValueError('ObservationGenerationFieldsMismatch')
    criteria=[c['id'] for c in definition['criteria']]
    declared=contracts['validation']['parameters']['properties']['criteria']['items']['properties']['id']['enum']
    if len(criteria)!=len(set(criteria)) or len(declared)!=len(set(declared)) or set(criteria)!=set(declared):
        raise ValueError('CriterionSchemaMismatch')
    admitted=set(definition['responsibility_admission'])
    roles=contracts['responsibility']['parameters']['properties']['segments']['items']['properties']['role']['enum']
    if admitted!=set(roles):raise ValueError('ResponsibilityRoleSchemaMismatch')
    profile=definition.get('arithmetic_extraction_format')
    encoding=definition.get('candidate_encoding')
    if encoding not in (None,SPAN_FORMAT):raise ValueError('UnsupportedCandidateEncoding')
    indexed=encoding==SPAN_FORMAT
    quotes=definition.get('criterion_quote_encoding')
    if quotes not in (None,QUOTE_SELECTIONS) or (quotes is not None and not indexed):
        raise ValueError('UnsupportedCriterionQuoteEncoding')
    if indexed and (profile not in (FORMAT_V2,OBSERVER_FORMAT) or definition.get('source_encoding')!='field-handles-v1'):
        raise ValueError('IndexedCandidateProfileMismatch')
    if profile is not None:
        if profile not in (FORMAT,FORMAT_V2,OBSERVER_FORMAT):raise ValueError('UnsupportedArithmeticExtractionFormat')
        if profile in (FORMAT_V2,OBSERVER_FORMAT) and not indexed:raise ValueError('IndexedCandidateProfileRequired')
        if definition['validation_format']!='arithmetic-linked-v6' or 'arithmetic_mapping' not in criteria:
            raise ValueError('RequiredArithmeticMappingReviewMissing')
        fields=list(schema['properties'])
        expected=observer_contract() if profile==OBSERVER_FORMAT else extraction_contract_v2() if indexed else extraction_contract(fields)
        if contracts['extraction']!=expected:raise ValueError('ExpressionContractMismatch')
        validation=contracts['validation']['parameters']['properties']
        exact={'type':'string','enum':fields}
        field_schemas=[validation['reviewed_fields']['items']]
        location_schemas=[validation['criteria']['items']['properties']['quotes']['items']['properties'],
            validation['claims']['items']['properties'],
            contracts['responsibility']['parameters']['properties']['segments']['items']['properties']]
        if indexed:
            for props in location_schemas:
                if ('field' in props or 'text' in props
                        or props.get('span_ids')!={'type':'array','items':{'type':'string'}}):
                    raise ValueError('IndexedCandidateContractMismatch')
        else:
            field_schemas.extend(props['field'] for props in location_schemas)
        if any(s!=exact for s in field_schemas):raise ValueError('ExactCandidateFieldSchemaMismatch')
    if definition.get('validation_dimensions') is not None:check_dimensions(definition)
    return {'status':'PASS','criteria':criteria,'responsibility_roles':roles,'schemas_checked':len(contracts)}
