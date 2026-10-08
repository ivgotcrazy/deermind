"""Offline readiness of the finite exit plan, including exact historical request replay."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import argparse
import io
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from foundation.cases import EvidenceRecorder
from foundation.composition_cases import CompositionWorld
from foundation.exit_campaign import CONFIG, ROOT, audit_messages, read, run_schedule
from foundation.llm import DeepSeekAdapter, LLMConfig, load_config
from foundation.protocol_preflight import check_observation_contract
from foundation.security_cases import SecurityWorld, envelope, request
from foundation.serial_cases import SerialWorld
from run_composition_validation import execute_branch as composition_replay
from run_security_validation import run_branch as security_replay
from run_serial_validation import execute_branch as serial_replay
from run_foundation import manifest

PACK = ROOT / 'src/spike/review-packages/spike-exit-v1'
RUN = ROOT / 'src/spike/runs/spike-exit-v1'


def write(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def hashed(path):
    return sha256(path.read_bytes()).hexdigest()


class ScriptedTransport:
    """Synthetic interface fixtures; never claim that these outputs interpret text correctly."""
    def __init__(self):
        self.spec = {}
        self.calls = 0

    def before_case(self, spec):
        self.spec = spec

    def __call__(self, url, key, wire, timeout):
        self.calls += 1
        audit_messages(wire['messages'])
        contract = wire['tools'][0]['function']
        name = contract['name']
        body = json.loads(wire['messages'][1]['content'])
        properties = contract['parameters']['properties']
        negative = self.spec.get('expected_semantic') == 'FAIL'
        if name == 'submit_observation':
            value = {'description': 'Explicit offline interface fixture; no semantic capability evidence.'}
        elif name == 'submit_responsibility':
            value = {'segments': [{'field': 'description', 'text': body['candidate']['description'],
                'role': 'ability_inference' if negative else 'local_observation', 'rationale': 'SCRIPTED ONLY'}]}
        elif name == 'submit_extraction':
            extraction = properties['segments']['items']['properties']
            keyname = 'expressions' if 'expressions' in extraction else 'assertions'
            value = {'segments': [{'field': 'description', 'text': body['candidate']['description'],
                                  'coverage': 'COMPLETE', keyname: []}]}
        elif name == 'submit_policy':
            constraint = next(i['content'] for i in body if i['kind'] == 'ActivityConstraints')
            permitted = constraint['allowed_action_refs']
            action = next((i for i in body if i['kind'] == 'ActionSemantic' and i['ref'] in permitted), None)
            if self.spec.get('variant') == 'E1-wait':
                action = None
            value = {'outcome': 'Execute' if action else 'NoIntervention',
                'action_identity': action['ref']['identity'] if action else '',
                'action_revision': action['ref']['revision'] if action else '',
                'exact_payload': action['content']['exact_payload'] if action else '',
                'executor_target': action['content']['executor_target'] if action else '',
                'episode': constraint['episode'], 'rationale': 'SCRIPTED ONLY',
                'context_refs': [body[0]['ref']], 'expected_disclosure': 'SCRIPTED ONLY',
                'uncertainty': 'SCRIPTED ONLY', 'defer_condition': ''}
        elif name == 'submit_policy_utility':
            value = {'scores': [{'id': r, 'status': self.spec.get('expected_utility', 'PASS'),
                                'reason': 'SCRIPTED ONLY'} for r in body['rubric']]}
        elif name == 'submit_tool_request':
            value = envelope(request())
            value['decision'] = 'REFUSE'
        elif 'checks' in properties:
            status = 'FAIL' if negative else 'PASS'
            registry = body['quote_registry']
            cq = next(r for r in registry['candidate'] if r['field'] == 'rationale')
            sq = registry['source'][0]
            rules = ['S1', 'S2', 'S3', 'S4', 'S5']
            value = {k: body[k] for k in ('candidate_digest', 'context_id', 'rule_ref', 'material_record_ref')}
            value.update(reviewed_fields=list(body['candidate']),
                findings=[{'id': 'f1', 'rules': rules, 'relation': 'CONTRADICTED' if negative else 'SUPPORTED',
                    'candidate_quotes': [{'handle': cq['handle']}], 'source_quotes': [{'handle': sq['handle']}],
                    'gap_ids': [], 'rationale': 'SCRIPTED ONLY'}], review_material_gaps=[],
                checks=[{'id': r, 'status': status, 'reason_code': 'CONTENT_DEFECT' if negative else 'SATISFIED',
                         'finding_ids': ['f1'], 'rationale': 'SCRIPTED ONLY'} for r in rules],
                status=status, rationale='SCRIPTED ONLY')
        elif 'criteria' in properties:
            text = body['candidate']['description']
            ids = properties['criteria']['items']['properties']['id']['enum']
            sources = properties['claims']['items']['properties']['sources']['items']['enum']
            value = {'reviewed_fields': ['description'], 'criteria': [
                {'id': r, 'status': 'FAIL' if negative and r == 'boundary' else 'PASS',
                 'quotes': [{'field': 'description', 'text': text}], 'rationale': 'SCRIPTED ONLY'} for r in ids],
                'claims': [{'field': 'description', 'text': text, 'kind': 'paraphrase', 'reported_quote': None,
                    'status': 'PASS', 'sources': [sources[0]], 'rationale': 'SCRIPTED ONLY', 'support': 'supported',
                    'attribution': {'speaker': 'system', 'stance': 'endorsed'},
                    'boundary_status': 'FAIL' if negative else 'PASS', 'inspection_scope': 'COMPLETE_CONTEXT'}]}
        else:
            value = {'status': 'PASS', 'rationale': 'SCRIPTED ONLY'}
        return {'choices': [{'finish_reason': 'tool_calls', 'message': {'content': None,
            'tool_calls': [{'id': 'offline', 'type': 'function', 'function': {
                'name': name, 'arguments': json.dumps(value, ensure_ascii=False)}}]}}]}


class ExactReplay:
    """Preserved responses; only ActionOccurrence generated refs/ticks may be rebound."""
    def __init__(self, file):
        self.rows = [json.loads(line) for line in file.read_text(encoding='utf-8').splitlines()
                     if json.loads(line).get('kind') == 'model_execution']
        self.index = 0
        self.mismatch = None
        self.ref_mapping = {}
        self.runtime_differences = []

    def mapped_messages(self, messages, current):
        old = deepcopy(messages)
        if len(old) != len(current) or any(a['role'] != b['role'] for a, b in zip(old, current)):
            return old
        for a, b in zip(old, current):
            if a['role'] != 'user':
                continue
            value, target = json.loads(a['content']), json.loads(b['content'])
            # Generation Context array and legacy semantic-review Context use the same source view.
            originals = value if isinstance(value, list) else value.get('context', [])
            currents = target if isinstance(target, list) else target.get('context', [])
            for index, (source, now) in enumerate(zip(originals, currents)):
                if source.get('kind') != 'ActionOccurrence' or now.get('kind') != 'ActionOccurrence':
                    continue
                pairs = [(source.get('ref'), now.get('ref'), 'ref')]
                for field in ('intent_ref', 'acknowledgement_ref'):
                    pairs.append((source.get('content', {}).get(field), now.get('content', {}).get(field), field))
                for prior, present, field in pairs:
                    if prior is None or present is None or prior == present:
                        continue
                    if (prior.keys() != present.keys() or prior['space'] != present['space']
                            or prior['revision'] != present['revision']
                            or len(prior['identity']) != 32 or len(present['identity']) != 32
                            or any(ch not in '0123456789abcdef' for ch in prior['identity'] + present['identity'])):
                        continue
                    old_id, new_id = prior['identity'], present['identity']
                    if (old_id in self.ref_mapping and self.ref_mapping[old_id] != new_id
                            or new_id in self.ref_mapping.values() and self.ref_mapping.get(old_id) != new_id):
                        raise ValueError('ReplayReferenceNotBijective')
                    self.ref_mapping[old_id] = new_id
                    prior['identity'] = new_id
                    self.runtime_differences.append({'call': self.index, 'source_index': index, 'field': field,
                                                    'old_identity': old_id, 'current_identity': new_id})
                disclosure, current_disclosure = source.get('content', {}).get('actual_disclosure', {}), now.get('content', {}).get('actual_disclosure', {})
                if ('rendered_at' in disclosure and 'rendered_at' in current_disclosure
                        and disclosure['rendered_at'] != current_disclosure['rendered_at']
                        and type(disclosure['rendered_at']) is int and type(current_disclosure['rendered_at']) is int):
                    self.runtime_differences.append({'call': self.index, 'source_index': index, 'field': 'actual_disclosure.rendered_at',
                        'old_tick': disclosure['rendered_at'], 'current_tick': current_disclosure['rendered_at']})
                    disclosure['rendered_at'] = current_disclosure['rendered_at']
            a['content'] = json.dumps(self.remap_return_refs(value), ensure_ascii=False)
        return old

    def remap_return_refs(self, value):
        if isinstance(value, dict):
            if set(value) == {'space', 'identity', 'revision'} and value['identity'] in self.ref_mapping:
                return {**value, 'identity': self.ref_mapping[value['identity']]}
            return {k: self.remap_return_refs(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.remap_return_refs(v) for v in value]
        return value

    def __call__(self, url, key, wire, timeout):
        if self.index >= len(self.rows):
            raise ValueError('ReplayRequestedExtraCall')
        old = self.rows[self.index]
        self.index += 1
        mapped = self.mapped_messages(old['messages'], wire['messages'])
        def same_messages(a, b):
            return len(a) == len(b) and all(x['role'] == y['role'] and
                (json.loads(x['content']) == json.loads(y['content']) if x['role'] == 'user' else x['content'] == y['content'])
                for x, y in zip(a, b))
        if not same_messages(mapped, wire['messages']):
            self.mismatch = {'old': old['messages'], 'current': wire['messages']}
            raise ValueError('ReplaySourceContentMismatch')
        if {k: wire['tools'][0]['function'][k] for k in ('name', 'parameters')} != old['output_contract']:
            raise ValueError('ReplayOutputContractMismatch')
        public = old['config']
        if (url != public['base_url'] + '/chat/completions' or wire['model'] != public['model']
                or wire['max_tokens'] != public['max_output_tokens'] or wire['temperature'] != public['temperature']
                or wire['thinking'] != {'type': public['thinking']} or timeout != public['timeout_seconds']):
            raise ValueError('ReplayModelConfigMismatch')
        if old['status'] != 'COMPLETED':
            raise ValueError('OnlyCompletedHistoricalPathCanReplay')
        calls = deepcopy(old.get('tool_calls'))
        if calls:
            for call in calls:
                original = json.loads(call['function']['arguments'])
                call['function']['arguments'] = json.dumps(self.remap_return_refs(original), ensure_ascii=False)
        return {'choices': [{'finish_reason': old['finish_reason'], 'message': {
            'content': old['content'], 'tool_calls': calls}}],
            'id': old.get('response_id'), 'model': old.get('model'),
            'system_fingerprint': old.get('system_fingerprint'), 'usage': old.get('usage')}


def historical_compatibility(folder, plan):
    """Replay the 46 completed paths offline to test current applicability, not fresh LLM quality."""
    policy = read(plan['original_fixtures']['E1'])
    definition = read(plan['protocols']['mechanism_policy'])
    sec_fixture = read(plan['original_fixtures']['F2'])
    evidence = EvidenceRecorder(folder / 'baseline.jsonl')
    try:
        bases = {'E2': SerialWorld(evidence, definition, policy),
                 'F2': SecurityWorld(evidence, read(plan['protocols']['security'])),
                 'X1X2': CompositionWorld(evidence, definition, policy)}
    finally:
        evidence.close()
    result = []
    for group, run in [('E2', 'serial-e2-v1'), ('F2', 'security-f-v1'), ('X1X2', 'composition-x1-x2-v1')]:
        original = ROOT / 'src/spike/runs' / run
        summary = read((original / 'summary.json').relative_to(ROOT).as_posix())
        for row in summary['runs']:
            if row.get('coverage') != 'COMPLETE' or row.get('result') != 'PASS' or group == 'F2' and row['case'] != 'F2':
                continue
            variant = row.get('branch', row.get('variant'))
            repetition = row['repetition']
            file = original / f'{repetition}-{variant}.jsonl'
            replay = ExactReplay(file)
            oldconfig = replay.rows[0]['config']
            config = LLMConfig('OFFLINE-REPLAY', base_url=oldconfig['base_url'], model=oldconfig['model'],
                max_calls=len(replay.rows), max_output_tokens=oldconfig['max_output_tokens'], timeout_seconds=oldconfig['timeout_seconds'])
            e = EvidenceRecorder(folder / f'{group}-{repetition}-{variant}.jsonl')
            try:
                if group == 'E2':
                    actual = serial_replay(bases[group], e, variant, repetition, config, replay)
                elif group == 'F2':
                    spec = next(v for v in sec_fixture['variants'] if v['id'] == variant)
                    actual = security_replay(bases[group], e, spec, repetition, config, replay)
                else:
                    actual = composition_replay(bases[group], e, variant, repetition, config, replay)
                matched = actual['result'] == 'PASS' and actual['coverage'] == 'COMPLETE' and replay.index == len(replay.rows)
                result.append({'group': group, 'variant': variant, 'repetition': repetition,
                    'original_file': file.relative_to(ROOT).as_posix(), 'original_sha256': hashed(file),
                    'status': 'REQUEST_AND_MECHANISM_COMPATIBLE' if matched else 'APPLICABILITY_NOT_PROVEN',
                    'comparison': 'GENERATED_REF_AND_TICK_MAPPING' if replay.runtime_differences else 'EXACT_REQUEST',
                    'original_model_calls': len(replay.rows), 'replayed_requests': replay.index,
                    'request_mismatch': replay.mismatch,
                    'runtime_reference_and_tick_differences': replay.runtime_differences,
                    'result': actual})
            finally:
                e.close()
    return {'status': 'PASS' if len(result) == 46 and all(r['status'] == 'REQUEST_AND_MECHANISM_COMPATIBLE' for r in result) else 'FAIL',
            'expected_paths': 46, 'paths': result, 'fresh_model_calls': 0,
            'claim': 'Same original prompt, source meanings/values, output schema and model configuration. Only generated UUID refs and the mock rendered_at tick of corresponding ActionOccurrence may change, explicitly retained; all remaining request data must compare equal. Preserved returns only rebind exact structured refs. Current mechanisms reproduce all required checks. This proves bounded applicability, not byte-identical wire messages, exact old source reconstruction or fresh semantic reliability.'}


def preflight(plan):
    if len(plan['schedule']) != 66 or len({s['id'] for s in plan['schedule']}) != 66 or sum(s['max_calls'] for s in plan['schedule']) != 375:
        raise ValueError('ExitScheduleBudgetMismatch')
    for path, expected in {**plan['fixed_protocol_sha256'], **plan['fixed_fixture_sha256']}.items():
        if hashed(ROOT / path) != expected:
            raise ValueError('ExitPinnedInputMismatch:' + path)
    for name in ('observation', 'formation_observation', 'request'):
        check_observation_contract(read(plan['protocols'][name]))
    if plan['budget'] != {'max_calls': 375, 'wall_time_seconds': 3600, 'transport_retries': 0, 'replacement_cases': 0}:
        raise ValueError('ExitHardBudgetMismatch')
    return {'scheduled_executions': 66, 'derived_boundaries': 4, 'max_calls': 375, 'network_calls': 0}


def prepare(folder):
    plan = read(CONFIG.relative_to(ROOT).as_posix())
    preflight(plan)
    frozen = manifest(ROOT)['content_sha256']
    frozen[plan['plan_document']] = hashed(ROOT / plan['plan_document'])
    frozen[CONFIG.relative_to(ROOT).as_posix()] = hashed(CONFIG)
    for p in plan['fixed_protocol_sha256'] | plan['fixed_fixture_sha256']:
        frozen[p] = hashed(ROOT / p)
    for p in (ROOT / 'src/spike').glob('*.py'):
        frozen[p.relative_to(ROOT).as_posix()] = hashed(p)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'cases').mkdir()
    (folder / 'compatibility').mkdir()
    (folder / 'mechanical').mkdir()
    network_attempts = []
    def blocked(*args, **kwargs):
        network_attempts.append('BLOCKED')
        raise RuntimeError('OfflineNetworkForbidden')
    transport = ScriptedTransport()
    adapter = DeepSeekAdapter(LLMConfig('OFFLINE-SCRIPTED', base_url=plan['model']['provider_endpoint'],
        max_calls=375, max_output_tokens=4096), transport)
    output = io.StringIO()
    with patch('socket.socket.connect', blocked), patch('socket.create_connection', blocked):
        batch = run_schedule(plan, adapter, lambda id: EvidenceRecorder(folder / 'cases' / (id + '.jsonl')),
            before_case=transport.before_case, content_review=lambda *args: True)
        compatibility = historical_compatibility(folder / 'compatibility', plan)
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'src/spike/tests'))
        import test_exit_campaign
        test_exit_campaign.ExitCampaignTests.artifact_directory = folder / 'mechanical'
        tests = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
        test_exit_campaign.ExitCampaignTests.artifact_directory = None
    changed = [p for p, h in frozen.items() if hashed(ROOT / p) != h]
    for record in adapter.records:
        audit_messages(record['messages'])
    maximum = max((len(json.dumps(r['messages'], ensure_ascii=False)) for r in adapter.records), default=0)
    passed = (batch['stop_reason'] is None and compatibility['status'] == 'PASS' and tests.wasSuccessful()
              and not changed and not network_attempts and maximum <= 16000)
    write(folder / 'actual-requests.json', adapter.records)
    write(folder / 'scripted-results.json', batch)
    write(folder / 'historical-compatibility.json', compatibility)
    (folder / 'unit-tests.txt').write_text(output.getvalue(), encoding='utf-8')
    write(folder / 'schedule.json', plan['schedule'])
    mechanical = {
        'missing_review': ['test_boundary.BoundaryTests.test_self_attestation_missing_failed_unresolved_or_foreign_review_is_rejected'],
        'call_or_contract_failure': ['test_validation_dimensions.ValidationDimensionTests.test_failure_at_each_stage_preserves_completed_checks_and_unrun_tail',
                                    'test_validation_dimensions.ValidationDimensionTests.test_wrong_field_is_failed_execution_not_completed_semantic_fail'],
        'unresolved': ['test_llm.LLMBoundaryTests.test_review_unresolved_blocks_standing'],
        'untrusted_record': ['test_exit_campaign.ExitCampaignTests.test_untrusted_validation_execution_cannot_grant_standing'],
        'model_self_pass': ['test_boundary.BoundaryTests.test_self_attestation_missing_failed_unresolved_or_foreign_review_is_rejected'],
        'changed_candidate': ['test_boundary.BoundaryTests.test_payload_dependency_and_expected_head_edits_cannot_reuse_pass'],
        'wrong_rule': ['test_exit_campaign.ExitCampaignTests.test_observation_wrong_rule_or_context_cannot_commit'],
        'wrong_context': ['test_exit_campaign.ExitCampaignTests.test_observation_wrong_rule_or_context_cannot_commit'],
        'stale_basis': ['test_boundary.BoundaryTests.test_current_correction_invalidates_frozen_candidate_without_rebinding'],
        'downstream_audit_or_unvalidated_content': [
            'test_content_projection.ContentProjectionTests.test_actual_generation_validation_and_manifest_use_projected_fields',
            'test_content_projection.ContentProjectionTests.test_failed_unresolved_and_unsubmitted_candidates_have_no_formal_input',
            'test_content_projection.ContentProjectionTests.test_seeded_derived_label_without_real_commit_proof_is_rejected']}
    old_files = [ROOT / 'src/spike/runs/context-projection-v1/cases' / (name + '.jsonl') for name in (
        'test_actual_generation_validation_and_manifest_use_projected_fields',
        'test_failed_unresolved_and_unsubmitted_candidates_have_no_formal_input',
        'test_seeded_derived_label_without_real_commit_proof_is_rejected')]
    write(folder / 'a2-mechanical-obligations.json', {'obligations': mechanical, 'unit_result': 'unit-tests.txt',
        'existing_actual_downstream_evidence_sha256': {p.relative_to(ROOT).as_posix(): hashed(p) for p in old_files},
        'additional_binding_evidence': [p.name for p in (folder / 'mechanical').glob('*.jsonl')],
        'scope': 'Shared mechanical checks only; no claim that LLM PASS implies semantically correct content.'})
    for p in old_files:
        frozen[p.relative_to(ROOT).as_posix()] = hashed(p)
    summary = {'status': 'OFFLINE_READY' if passed else 'NOT_READY', 'external_model_calls': 0,
        'blocked_network_attempts': len(network_attempts), 'scripted_calls': adapter.calls,
        'scripted_cases_completed': sum(r['execution'] == 'COMPLETED' for r in batch['rows']),
        'scripted_stop_reason': batch['stop_reason'], 'maximum_message_chars': maximum,
        'historical_compatibility_status': compatibility['status'], 'historical_paths_replayed': len(compatibility['paths']),
        'tests_run': tests.testsRun, 'test_failures': len(tests.failures), 'test_errors': len(tests.errors),
        'changed_frozen_sources': changed, 'semantic_support_claimed': False,
        'independent_blind_labels': False, 'real_execution_started': False, 'original_full_cases_completed': 9,
        'original_A2': 'DENIED', 'gate_E': 'OPEN', 'gate_F': 'OPEN'}
    write(folder / 'summary.json', summary)
    write(folder / 'manifest.json', {'source_sha256': frozen, 'configuration_sha256': hashed(CONFIG),
        'artifact_sha256': {p.relative_to(folder).as_posix(): hashed(p) for p in sorted(folder.rglob('*')) if p.is_file()},
        'status': summary['status'], 'external_model_calls': 0})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=PACK)
    args = parser.parse_args()
    summary = prepare(args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary['status'] == 'OFFLINE_READY' else 1


if __name__ == '__main__':
    raise SystemExit(main())
