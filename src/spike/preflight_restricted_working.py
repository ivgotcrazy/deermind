"""Offline contract/budget checks only; no credentials, transport or execution mode."""
import json
from hashlib import sha256
from pathlib import Path

from foundation.protocol_preflight import check_observation_contract
from foundation.structured_output import check_schema

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'src/spike/fixtures/restricted-working-v1.json'


def preflight():
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    schemas = 0
    definitions = {}
    for binding in config['protocol_bindings']:
        raw = (ROOT / binding['path']).read_bytes()
        if sha256(raw).hexdigest() != binding['sha256']:
            raise ValueError('FrozenWorkingProtocolChanged:' + binding['role'])
        definition = json.loads(raw)
        if binding['protocol_ref'] != {'space':'canonical', 'identity':definition['identity'],
                                       'revision':definition['version']}:
            raise ValueError('WorkingProtocolRefMismatch')
        if binding['semantic_rule_ref']['revision'] != definition['version']:
            raise ValueError('WorkingRuleRevisionMismatch')
        definitions[binding['role']] = definition
        if binding['role'] != 'policy':
            check_observation_contract(definition)
        for contract in definition['output_contracts'].values():
            check_schema(contract['parameters'])
            schemas += 1
    policy = definitions['policy']
    declared = policy['runtime_binding_requirement']
    binding = next(b for b in config['protocol_bindings'] if b['role'] == 'policy')
    if (policy['legality_profile'] != 'policy-admission-v1'
            or declared['protocol_ref'] != binding['protocol_ref']
            or declared['semantic_rule_ref'] != binding['semantic_rule_ref']
            or declared['utility_rule_ref'] != config['policy_utility_rule_ref']):
        raise ValueError('WorkingPolicyBindingMismatch')
    if config['profile']['protocols'] != [b['protocol_ref'] for b in config['protocol_bindings']]:
        raise ValueError('WorkingScopeProtocolMismatch')
    normal, controls = config['normal_cases'], config['fixed_review_controls']
    ids = [c['id'] for c in controls + normal]
    if len(ids) != len(set(ids)) or config['execution_order'] != ids:
        raise ValueError('WorkingCaseOrderMismatch')
    if any(c['input_profile'] not in ('work', 'request') for c in normal):
        raise ValueError('WorkingInputProfileMissing')
    if any(c['source_case'] not in [n['id'] for n in normal] for c in controls):
        raise ValueError('WorkingControlSourceMissing')
    budget = config['budget']
    planned = len(normal)*budget['normal_case_calls'] + sum(c['normal_calls'] for c in controls)
    maximum = len(normal)*budget['normal_case_max_calls'] + sum(c['max_calls'] for c in controls)
    if (planned, maximum) != (budget['planned_calls'], budget['max_calls']):
        raise ValueError('WorkingBudgetMismatch')
    if budget['repetitions'] != 1 or budget['transport_retries'] or budget['replacement_cases']:
        raise ValueError('WorkingUnboundedExecution')
    return {'status':'OFFLINE_CONTRACT_PASS_RUNTIME_INTEGRATION_REQUIRED',
            'configuration_sha256':sha256(CONFIG.read_bytes()).hexdigest(),
            'protocols_verified':len(definitions), 'schemas_checked':schemas,
            'normal_cases':len(normal), 'fixed_controls':len(controls),
            'planned_calls':planned, 'max_calls':maximum,
            'wall_time_seconds':budget['wall_time_seconds'], 'external_model_calls':0,
            'runtime_requests_audited':False, 'execution_authorized':False,
            'independent_semantic_review':False}


if __name__ == '__main__':
    print(json.dumps(preflight(), ensure_ascii=False, indent=2))
