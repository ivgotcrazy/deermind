"""One finite exit schedule; shared boundaries, explicit versions, no semantic heuristics."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

from .activity_cases import ActivityWorld, PathIncomplete, run_boundary
from .boundary import ContextInput, Protocol, digest
from .cases import seed
from .composition_cases import CompositionWorld, run_composition
from .formation_cases import FormationWorld, run_case as formation_case
from .llm import ModelFailure
from .policy_cases import PolicyWorld, run_policy_case
from .records import Ref, Space, VersionContext, json_value
from .runtime import Compatibility, ContractError, Decision
from .security import AuthorityGrant, DataUseGrant
from .security_cases import SecurityWorld
from .serial_cases import SerialWorld, run_branch as serial_branch
from .working_campaign import CallBudget

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / 'src/spike/fixtures/spike-exit-v1.json'


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


class ExitActivityWorld(ActivityWorld):
    """Reuse the X5 lifecycle with explicitly selected, unmodified v13/request-v2/v5."""
    def install_protocol(self, name, kind, path, inputs):
        path = {'initial': 'observation-validation-v13.json',
                'new-work': 'observation-validation-v13.json',
                'request': 'observation-x5-request-v2.json',
                'policy': 'policy-exit-x5-v1.json'}[name]
        definition = read('src/spike/protocols/' + path)
        ref = Ref(Space.CANONICAL, definition['identity'], definition['version'])
        # initial and new-work share the same work Profile, declared before generation.
        existing = self.protocols.get('initial') if name == 'new-work' else None
        if existing:
            self.protocols[name] = existing
            self.versions[name] = self.versions['initial']
            return
        ref = seed(self.h, ref, kind='ReasoningProtocol', payload=definition)
        rule_ref = (Ref(**{**definition['runtime_binding_requirement']['semantic_rule_ref'], 'space': Space.CANONICAL}) if kind == 'PolicyOutcome'
                    else Ref(Space.CANONICAL, 'Exit-' + name + '-Rules', definition['version']))
        rule = seed(self.h, rule_ref, kind='SemanticValidationRules', payload={
            'format': definition['validation_format'], 'system': definition['validation_system'],
            'criteria': definition.get('criteria', [])})
        protocol = Protocol(ref, kind, 'Interaction', inputs,
            tuple(tuple(f) for f in definition.get('fields', [['description', 'string']])), rule, self.endpoint)
        self.runtime.register_protocol(protocol)
        bindings = (ref, rule)
        if kind == 'PolicyOutcome':
            utility = seed(self.h, Ref(**{**definition['runtime_binding_requirement']['utility_rule_ref'], 'space': Space.CANONICAL}), kind='PolicyUtilityRules',
                payload={'system': definition['utility_system'], 'rubric': definition['utility_rubric'], 'test_only': True})
            bindings += (utility,)
            declared = definition['runtime_binding_requirement']
            if (json_value(ref), json_value(rule), json_value(utility)) != tuple(
                    declared[k] for k in ('protocol_ref', 'semantic_rule_ref', 'utility_rule_ref')):
                raise ContractError('ExitX5PolicyBindingMismatch')
        self.protocols[name] = protocol
        basis = 'Exit-X5-' + name
        self.h.canonical.add_compatibility_fixture(Compatibility(basis, bindings, 'learner-A', 'learning', Decision.ALLOW))
        self.versions[name] = VersionContext(bindings, compatibility_basis=basis)
        self.security.install_authority(AuthorityGrant(basis + '-reason', 'interaction', 'learning', 'learner-A',
            (ref.identity,), ('reason', 'validate'), 100000))
        self.security.install_data(DataUseGrant(basis + '-validate', 'interaction', 'learning', 'learner-A',
            (kind,), ('validate',), (self.endpoint,), 'run', 'internal', 100000))


def close_world(world, evidence):
    """Failure settlement; never fabricate or execute a missing Policy."""
    sessions = getattr(world, 'sessions', None)
    if sessions:
        for turn in list(sessions.active.values()):
            phase = sessions.turns[turn]['phase']
            if phase == 'SETTLED':
                continue
            if phase != 'CLOSING':
                failure = world.runtime.execution('TurnFailure', 'learner-A',
                    {'turn_ref': json_value(turn), 'code': 'ExitCampaignStopped'})
                sessions.begin_close(turn, failure)
            sessions.finish_close(turn)
        evidence.check('failure closes all active turns', not sessions.active, True)


def observation_control(e, plan, spec, adapter):
    definition = read(plan['protocols']['formation_observation'])
    w = FormationWorld(definition, {'text': spec['work']})
    w.check_exclusion(e)
    e.capture(w.h, 'initial')
    candidate = w.runtime.propose(w.context, 'O', 'r1', spec['candidate'])
    e.emit('fixed_candidate', candidate=json_value(candidate), label_origin='HOST_ONLY_DEVELOPER')
    try:
        review = w.runtime.validate_with_llm(w.token, candidate, adapter)
        details = json.loads(review.details_json)
        e.emit('fixed_review', review=json_value(review))
        commit = w.runtime.commit(w.token, candidate, review.identity)
        e.emit('fixed_commit', outcome=json_value(commit))
        statuses = {c['id']: c['status'] for c in details['criteria']}
        responsibility = w.h.get(review.execution).payload.get('responsibility_result', {}).get('status')
        e.check('fixed overall semantic judgment', review.status, spec['expected_semantic'])
        for criterion, expected in spec['expected_criteria'].items():
            e.check('target criterion:' + criterion, statuses.get(criterion), expected)
        e.check('separate responsibility judgment', responsibility, spec['expected_responsibility'])
        e.check('formal outcome agrees with expected semantics', commit.status,
                'Committed' if spec['expected_semantic'] == 'PASS' else 'ValidationFailed')
        e.check('wrong semantic PASS cannot hide behind another gate',
                commit.status == 'Committed' and spec['expected_semantic'] != 'PASS', False)
        return {'result': 'PASS' if all(c['passed'] for c in e.checks) else 'FAIL',
                'coverage': 'COMPLETE', 'semantic_status': review.status, 'commit_status': commit.status,
                'review': details, 'responsibility_status': responsibility}
    finally:
        e.capture(w.h, 'final')


def policy_control(e, plan, spec, adapter):
    fixture = read(plan['original_fixtures']['E1'])
    definition = read(plan['protocols']['policy'])
    w = PolicyWorld(e, definition, fixture, fixture['variants'][1], rule_revision='v5')
    payload = {**plan['policy_control_base'], **spec['changes'], 'episode': w.episode,
               'context_refs': [json_value(w.input)]}
    candidate = w.runtime.propose(w.context, 'P', 'r1', payload)
    e.emit('fixed_candidate', candidate=json_value(candidate), label_origin='HOST_ONLY_DEVELOPER')
    review = w.runtime.validate_with_llm(w.tokens['interaction'], candidate, adapter)
    details = json.loads(review.details_json)
    e.emit('fixed_review', review=json_value(review))
    e.check('fixed overall semantic judgment', review.status, spec['expected_semantic'])
    statuses = {c['id']: c['status'] for c in details['checks']}
    if spec.get('required_any_fail'):
        e.check('target defect actually identified', any(statuses.get(r) == 'FAIL' for r in spec['required_any_fail']), True)
    # Stop before further scoring if the targeted check is already wrong.
    if all(c['passed'] for c in e.checks):
        utility = w.h.get(w.policy_runtime.utility_review(w.tokens['interaction'], candidate, adapter)).payload
        e.emit('fixed_utility', value=utility)
        e.check('fixed utility judgment', utility['status'], spec['expected_utility'])
    e.check('controls create no formal Policy or effects', w.h.get(candidate.record.ref) is None, True)
    e.capture(w.h, 'final')
    return {'result': 'PASS' if all(c['passed'] for c in e.checks) else 'FAIL', 'coverage': 'COMPLETE',
            'semantic_status': review.status, 'review': details}


def execute(e, plan, spec, adapter):
    group = spec['group']
    if group == 'A2':
        return observation_control(e, plan, spec, adapter), {}
    if group == 'E1-controls':
        return policy_control(e, plan, spec, adapter), {}
    if group == 'A1':
        definition = read(plan['protocols']['formation_observation'])
        variant = next(v for v in read(plan['original_fixtures']['A1'])['variants'] if v['id'] == spec['variant'])
        return formation_case(e, definition, variant, spec['repetition'], adapter), {}
    if group == 'E1-normal':
        fixture = read(plan['original_fixtures']['E1'])
        variant = next(v for v in fixture['variants'] if v['id'] == spec['variant'])
        return run_policy_case(e, read(plan['protocols']['policy']), fixture, variant,
                               spec['repetition'], adapter, rule_revision='v5'), {}
    fixture = read(plan['original_fixtures']['E1'])
    old_policy = read(plan['protocols']['mechanism_policy'])
    w = None
    try:
        if group == 'E2':
            w = SerialWorld(e, old_policy, fixture)
            injection = {'calls': 0}
            def inject():
                if not injection['calls']:
                    injection['calls'] += 1
                    w.runtime.execution('PolicyInFlight', 'learner-A', {'turn_ref': json_value(w.turn),
                        'context_id': w.context.identity, 'model_call': adapter.records[-1]['execution_id']})
                    w.queue_second()
            adapter.before_request = inject
            row = serial_branch(w, 'A-queue', adapter, injection)
        elif group in ('X1', 'X2'):
            w = CompositionWorld(e, old_policy, fixture)
            injection = {'calls': 0}
            def inject():
                if not injection['calls']:
                    injection['calls'] += 1
                    w.runtime.execution('PolicyInFlight', 'learner-A', {'turn_ref': json_value(w.turn),
                        'context_id': w.context.identity, 'model_call': adapter.records[-1]['execution_id']})
                    if group == 'X1':
                        w.queue_next()
                        w.external_correction()
                    else:
                        w.activate_v2()
            adapter.before_request = inject
            row = run_composition(w, spec['variant'], adapter, injection)
        elif group == 'F2':
            security_fixture = read(plan['original_fixtures']['F2'])
            variant = next(v for v in security_fixture['variants'] if v['id'] == spec['variant'])
            w = SecurityWorld(e, read(plan['protocols']['security']))
            w.prepare(variant)
            injected = w.branch(e)
            w.controls()
            if any(not c['passed'] for c in e.checks):
                raise ContractError('ExitSecurityPositiveControlFailed')
            candidate = w.runtime.generate_with_llm(w.token, w.context, adapter, identity='F-model-request')
            e.emit('model_candidate', candidate=json_value(candidate))
            result = w.check_dispatch(candidate, 'real-model')
            denial = injected.check_dispatch(injected.injected(variant['attack']), 'injected-attack', expected='DENIED')
            e.capture(injected.h, 'injected_final')
            row = {'coverage': 'COMPLETE', 'model_result': result['status'], 'injected_result': denial['status']}
        elif group == 'X5':
            w = ExitActivityWorld(e)
            injected = [False]
            def inject():
                if not injected[0]:
                    injected[0] = True
                    w.queue_teaching()
            adapter.before_request = inject
            row = w.run_path(adapter)
            return row, w.pending_snapshots
        else:
            raise ContractError('UnknownExitGroup')
        row['result'] = 'PASS' if row.get('coverage') == 'COMPLETE' and all(c['passed'] for c in e.checks) else 'NON_SUCCESS'
        return row, {}
    finally:
        adapter.before_request = lambda: None
        if w:
            close_world(w, e)
            e.capture(w.h, 'final')


class ExitBudget(CallBudget):
    """One adapter, global and per-case limits, exact outbound label isolation."""
    def __init__(self, adapter, budget, **kwargs):
        super().__init__(adapter, budget, **kwargs)
        self.before_request = lambda: None

    def complete(self, messages, purpose, *, output_contract=None):
        audit_messages(messages)
        original_transport = self.adapter.transport
        def hook(*args):
            self.before_request()
            return original_transport(*args)
        self.adapter.transport = hook
        try:
            return super().complete(messages, purpose, output_contract=output_contract)
        finally:
            self.adapter.transport = original_transport


HOST_KEYS = {'expected_semantic', 'expected_utility', 'expected_criteria', 'expected_responsibility',
             'required_any_fail', 'required_content', 'label_origin', 'required_detection', 'source_case'}


def audit_messages(messages):
    def walk(value):
        if isinstance(value, dict):
            if HOST_KEYS.intersection(value):
                raise ContractError('ExitHostLabelsInRequest')
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
    for message in messages:
        if 'EXIT_HOST_ONLY_SENTINEL_72841' in message['content']:
            raise ContractError('ExitHostLabelsInRequest')
        if message['role'] == 'user':
            walk(json.loads(message['content']))


def run_schedule(plan, adapter, recorder_factory, *, before_case=lambda s: None,
                 content_review=lambda spec, row, records: False, clock=None):
    limited = ExitBudget(adapter, plan['budget'], **({'clock': clock} if clock else {}))
    rows, stop, snapshots = [], None, {}
    for spec in plan['schedule']:
        row = {'id': spec['id'], 'group': spec['group'], 'execution': 'NOT_RUN'}
        if stop is None:
            e = recorder_factory(spec['id'])
            start = len(adapter.records)
            try:
                before_case(spec)
                limited.begin_case(spec['max_calls'])
                result, pending = execute(e, plan, spec, limited)
                row.update(result, execution='COMPLETED')
                row['failed_checks'] = [c for c in e.checks if not c['passed']]
                if result.get('result') != 'PASS' or row['failed_checks']:
                    stop = 'CaseRequirementsNotMet:' + spec['id']
                elif not content_review(spec, row, adapter.records[start:]):
                    stop = 'ContentReviewNotAccepted:' + spec['id']
                else:
                    row['content_review'] = 'ACCEPTED_FOR_THIS_SCOPE'
                    for stage, world in pending.items():
                        snapshots.setdefault(stage, (spec['id'], world))
                if stop:
                    row['execution'] = 'FAILED'
            except Exception as exc:
                # Only bounded runtime exceptions have safe registered messages.
                row.update(execution='FAILED', failure_type=type(exc).__name__,
                           reason=str(exc) if isinstance(exc, (ModelFailure, ContractError)) else type(exc).__name__)
                stop = 'ExecutionFailure:' + spec['id'] + ':' + row['reason']
            finally:
                row['model_calls'] = len(adapter.records) - start
                for record in adapter.records[start:]:
                    e.emit('model_execution', **record)
                e.emit('case_result', **row)
                e.close()
        rows.append(row)
    boundaries = []
    for name in plan['boundaries']:
        stage = 'switch-teaching' if name == 'control-not-occurred' else 'explain'
        row = {'variant': name, 'result': 'INCONCLUSIVE', 'coverage': 'NOT_RUN', 'model_calls': 0}
        if stop is None and stage in snapshots:
            parent, world = snapshots[stage]
            e = recorder_factory(name)
            try:
                e.emit('real_snapshot_ancestry', parent_case=parent, stage=stage,
                       semantics='REAL_UNLESS_EXPLICIT_OFFLINE_RUN', model_calls=0)
                row.update(run_boundary(world, e, name), parent_case=parent)
                if row['result'] != 'PASS':
                    stop = 'BoundaryRequirementsNotMet:' + name
            except Exception as exc:
                row.update(result='FAIL', failure_type=type(exc).__name__)
                stop = 'BoundaryExecutionFailed:' + name
            finally:
                e.close()
        boundaries.append(row)
    return {'rows': rows, 'boundaries': boundaries, 'stop_reason': stop, 'model_calls': adapter.calls,
            'semantic_support_claimed': False, 'content_review_required': True,
            'original_full_cases_completed': 9, 'original_A2': 'DENIED', 'gate_E': 'OPEN', 'gate_F': 'OPEN'}
