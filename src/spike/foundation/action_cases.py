"""D1/D2 isolate real effects/lineage from explicitly scripted cognition."""
import json
from pathlib import Path
from uuid import uuid4

from .actions import ActionRuntime, exact_ref
from .boundary import ContextInput, Protocol
from .cases import seed
from .dependency_cases import DependencyWorld
from .records import Ref, Role, Space, VersionContext, json_value
from .runtime import Compatibility, Decision
from .security import AuthorityGrant, DataUseGrant, parameter

PROFILE = Path(__file__).resolve().parents[1] / 'fixtures/action-exposure-v1.json'


class ActionWorld(DependencyWorld):
    def __init__(self, evidence):
        super().__init__(evidence, branches=3)
        self.fixture = json.loads(PROFILE.read_text(encoding='utf-8'))
        self.episode = 'apple-episode'
        self.action = seed(self.h, Ref(Space.CANONICAL, 'HintCheckStep', 'v1'), kind='ActionSemantic',
                           payload={'executor_target': 'mock-display', 'fixture': 'D1/D2'})
        self.work = self.response('before', self.fixture['before_work'])
        self.add_protocol('PolicyOutcome', 'Interaction', ('Observation', 'ActionSemantic'),
            (('outcome', 'string'), ('action_identity', 'string'), ('action_revision', 'string'),
             ('exact_payload', 'string'), ('executor_target', 'string'), ('episode', 'string')))
        self.add_protocol('Evidence', 'Evaluation', ('Observation', 'ActionOccurrence', 'Claim'),
            (('description', 'string'), ('claim_ref', 'object'), ('independence', 'string'), ('impact', 'string')))
        self.actions = ActionRuntime(self.runtime)
        constraints = tuple((k, (parameter(k, value)[1],)) for k, value in {
            'exact_payload': self.fixture['hint'], 'executor_target': 'mock-display',
            'action_semantic_ref': json_value(self.action)}.items())
        self.security.install_authority(AuthorityGrant('D-effect-authority', 'interaction', 'learning', 'learner-A',
            (self.action.identity,), ('execute',), 100000, constraints))
        self.security.install_data(DataUseGrant('D-effect-data', 'interaction', 'learning', 'learner-A',
            ('ActionDisclosure',), ('execute',), ('mock-display',), 'run', 'learner', 100000))
        self.e.emit('D_setup', profile=self.fixture, grants=self.security.describe_grants())

    def add_protocol(self, kind, owner, inputs, fields):
        principal = owner.lower()
        protocol = seed(self.h, Ref(Space.CANONICAL, 'D-' + kind + '-Protocol', 'v1'), kind='ReasoningProtocol',
                        payload={'semantic_source': 'SCRIPTED-D-MECHANISM-FIXTURE'})
        rule = seed(self.h, Ref(Space.CANONICAL, 'D-' + kind + '-Rules', 'v1'), kind='SemanticValidationRules',
                    payload={'format': 'fixture'})
        compat = 'D-' + kind + '-compatible'
        self.h.canonical.add_compatibility_fixture(Compatibility(compat, (protocol, rule), 'learner-A', 'learning', Decision.ALLOW))
        self.protocols[kind] = Protocol(protocol, kind, owner, inputs, fields, rule)
        self.versions[kind] = VersionContext((protocol, rule), compatibility_basis=compat)
        self.runtime.register_protocol(self.protocols[kind])
        self.security.install_authority(AuthorityGrant('D-' + kind + '-reason', principal, 'learning', 'learner-A',
            (protocol.identity,), ('reason', 'validate'), 100000))
        self.security.install_data(DataUseGrant('D-' + kind + '-validate', principal, 'learning', 'learner-A',
            (kind,), ('validate',), ('reasoning-runtime',), 'run', 'internal', 100000))
        self.security.install_data(DataUseGrant('D-' + kind + '-commit', principal, 'learning', 'learner-A',
            (kind,), ('commit',), ('formal-state',), 'run', 'internal', 100000))

    def allow_reads(self):
        # Explicit trusted setup grants only the finite records in this synthetic learner's run.
        records = [r for space in Space for r in self.h.history_for(space).records('learner-A')]
        for principal in ('interaction', 'evaluation'):
            suffix = uuid4().hex
            self.security.install_authority(AuthorityGrant('D-read-' + suffix, principal, 'learning', 'learner-A',
                tuple({r.ref.identity for r in records}), ('read',), 100000))
            self.security.install_data(DataUseGrant('D-data-' + suffix, principal, 'learning', 'learner-A',
                tuple({r.kind for r in records}), ('read',), ('reasoning-runtime', 'exposure-runtime'), 'run', 'internal', 100000))

    def response(self, identity, text=None):
        return seed(self.h, Ref(Space.FACT, 'D-work-' + identity, '1'), kind='LearnerWorkSubmitted',
                    occurrence_key='D-work-' + identity, payload={'episode': self.episode,
                    'task': '6kg apples cost 42 yuan. What do 15kg cost?', 'text': text or self.fixture['after_work']})

    def commit_scripted(self, kind, identity, payload, inputs):
        self.h.clock.advance()
        self.allow_reads()
        protocol = self.protocols[kind]
        principal = protocol.owner.lower()
        token = self.tokens[principal]
        self.security.install_authority(AuthorityGrant('D-commit-' + uuid4().hex, principal, 'learning', 'learner-A',
            (identity,), ('commit',), 100000, tuple((k, (parameter(k, v)[1],)) for k, v in {'owner': protocol.owner, 'kind': kind}.items())))
        context = self.runtime.assemble(token, protocol.ref, 'learner-A', 'learner-A', 'learning',
            tuple(ContextInput(ref, Role.CANONICAL if ref.space == Space.CANONICAL else Role.FACTUAL if ref.space == Space.FACT else Role.EPISTEMIC) for ref in inputs), self.versions[kind])
        candidate = self.runtime.propose(context, identity, 'r1', payload)
        review = self.runtime.record_semantic_validation(token, candidate, 'PASS',
            'Predeclared D fixture interpretation; no language inference is implemented here.', 'SCRIPTED-D-MECHANISM-FIXTURE', fixture=True)
        self.e.emit('D_prepared', context=json_value(context), candidate=json_value(candidate), review=json_value(review))
        return self.finish((token, candidate, review))

    def prepare_action(self):
        self.before_observation = self.commit_scripted('Observation', 'D-O-before',
            {'description': 'The learner selected a unit-rate route and wrote an incorrect division result.'}, (self.work,))
        self.policy = self.commit_scripted('PolicyOutcome', 'D-policy', {'outcome': 'Execute',
            'action_identity': self.action.identity, 'action_revision': self.action.revision,
            'exact_payload': self.fixture['hint'], 'executor_target': 'mock-display', 'episode': self.episode},
            (self.before_observation, self.action))
        self.allow_reads()
        self.intent = self.actions.create_intent(self.tokens['interaction'], self.policy,
            expires_at=self.h.clock.now + 1000, idempotency_key='D-hint-once')
        self.e.emit('intent', value=json_value(self.h.get(self.intent)))
        return self.intent

    def execute(self, mode, partial_characters=None):
        ref = self.actions.execute(self.tokens['interaction'], self.intent, mode=mode, partial_characters=partial_characters)
        self.result_ref = ref
        self.e.emit('action_result', value=json_value(self.h.get(ref)))
        return self.h.get(ref).payload

    def exposure(self, response):
        self.allow_reads()
        view = self.actions.exposure_for(self.tokens['evaluation'], response)
        self.e.emit('exposure_view', value=view)
        return view


def d1(e):
    fixture = json.loads(PROFILE.read_text(encoding='utf-8'))
    for variant in fixture['D1_variants']:
        e.emit('variant', id=variant)
        w = ActionWorld(e)
        if variant == 'available_unused':
            response = w.response('after')
            view = w.exposure(response)
            e.check(variant + ': no selected action', [r.kind for r in w.h.executions.records() if r.kind == 'ActionIntent'], [])
            e.check(variant + ': no exposure', view['exposures'], [])
        else:
            w.prepare_action()
            response = w.response('early') if variant == 'response_before_hint' else None
            mode = {'selected_not_occurred': 'NOT_OCCURRED', 'partial': 'OCCUR_PARTIAL',
                    'indeterminate': 'INDETERMINATE'}.get(variant, 'OCCUR_FULL')
            result = w.execute(mode, partial_characters=4 if variant == 'partial' else None)
            response = response or w.response('after')
            view = w.exposure(response)
            expected = 'NotOccurred' if mode == 'NOT_OCCURRED' else 'Indeterminate' if mode == 'INDETERMINATE' else 'Occurred'
            e.check(variant + ': result category', result['status'], expected)
            e.check(variant + ': occurrence count', len(view['exposures']), int(expected == 'Occurred'))
            e.check(variant + ': factual admission only on acknowledged effect',
                    sum(r.kind == 'ActionOccurrence' for r in w.h.facts.records()), int(expected == 'Occurred'))
            if expected == 'Occurred':
                actual = view['exposures'][0]
                e.check(variant + ': exact actual payload', actual['payload'], fixture['hint'][:4] if mode == 'OCCUR_PARTIAL' else fixture['hint'])
                e.check(variant + ': completeness', actual['completeness'], 'PARTIAL' if mode == 'OCCUR_PARTIAL' else 'FULL')
                e.check(variant + ': temporal relation', actual['before_response'], variant != 'response_before_hint')
                e.check(variant + ': exact intent', actual['intent_ref'], json_value(w.intent))
            else:
                e.check(variant + ': uncertainty is retained', view['unconfirmed'][0]['status'], expected)
            w.allow_reads()
            again = ActionRuntime(w.runtime).execute(w.tokens['interaction'], w.intent, mode='OCCUR_FULL')
            e.check(variant + ': repeat returns historical terminal result', json_value(again), json_value(w.result_ref))
            e.check(variant + ': no duplicate occurrence', sum(r.kind == 'ActionOccurrence' for r in w.h.facts.records()), int(expected == 'Occurred'))
        e.check(variant + ': use is not inferred', view['learner_used_assistance'], 'NOT_INFERRED')
        e.check(variant + ': no exposure state model', any(r.kind == 'AssistanceExposureModel' for r in w.h.states.records()), False)
        w.preserve(w.h.states.records())


def d2(e):
    w = ActionWorld(e)
    w.prepare_action()
    result = w.execute('OCCUR_FULL')
    occurrence = exact_ref(result['occurrence_ref'])
    response = w.response('after')
    after = w.commit_scripted('Observation', 'D-O-after',
        {'description': 'The later work corrects the quotient to 7 and total to 105.'}, (response,))
    view = w.exposure(response)
    e.check('D2: actual localized hint precedes response', view['exposures'][0]['before_response'], True)
    refs = []
    for meaning in w.fixture['claim_interpretations']:
        claim = seed(w.h, Ref(Space.CANONICAL, meaning['identity'], 'v1'), kind='Claim', payload={'claim': meaning['claim']})
        ref = w.commit_scripted('Evidence', 'D-E-' + meaning['identity'], {
            'description': meaning['description'], 'claim_ref': json_value(claim),
            'independence': meaning['independence'], 'impact': meaning['impact']},
            (w.before_observation, after, occurrence, claim))
        refs.append(ref)
        evidence = w.h.get(ref)
        e.check(meaning['identity'] + ': explicit claim binding', evidence.payload['claim_ref'], json_value(claim))
        e.check(meaning['identity'] + ': declared relative interpretation', evidence.payload['impact'], meaning['impact'])
        e.check(meaning['identity'] + ': same exact response observation and hint occurrence',
                {d.target for d in evidence.dependencies} >= {after, occurrence, w.before_observation, claim}, True)
        e.check(meaning['identity'] + ': Evaluation owns Evidence', evidence.owner, 'Evaluation')
    e.check('D2: three different interpretations coexist', len({w.h.get(ref).payload['impact'] for ref in refs}), 3)
    e.check('D2: before-hint strategy basis is earlier than exposure',
            w.h.get(w.before_observation).recorded_at < view['exposures'][0]['rendered_at'], True)
    e.check('D2: no global assisted flag substitutes for meaning',
            any('assisted' in w.h.get(ref).payload for ref in refs), False)
    w.allow_reads()
    w.stage('D2: three Claim-relative Evidence records are independently current', {ref.identity: ref for ref in refs})
    w.preserve(w.h.states.records())


CASES = {'D1': d1, 'D2': d2}
