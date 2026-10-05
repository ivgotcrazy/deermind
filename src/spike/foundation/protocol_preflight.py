"""Check declared mechanical contracts before a bounded model campaign."""
from .structured_output import check_schema


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
    return {'status':'PASS','criteria':criteria,'responsibility_roles':roles,'schemas_checked':len(contracts)}
