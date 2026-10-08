"""Finite opt-in scope enforcement; scripted semantics, no provider calls."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from foundation.cases import EvidenceRecorder, seed
from foundation.records import Ref, Space, json_value
from foundation.runtime import ContractError
from foundation.serial_cases import SerialWorld
from foundation.working_entry import RestrictedEntry, WorkingScope
from test_turn_closure import local_transport
from foundation.llm import DeepSeekAdapter, LLMConfig
from run_serial_validation import load_design


class WorkingEntryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        self.e = EvidenceRecorder(Path(directory.name)/'scope.jsonl'); self.addCleanup(self.e.close)
        _, fixture, definition = load_design()
        self.w = SerialWorld(self.e, definition, fixture)
        self.profile = WorkingScope('FixedActivityEntry', 'v1', 'learner-A', 'learner-A', 'learning',
            (self.w.e2_protocol.ref,), self.w.constraints,
            tuple(Ref(Space(r['space']), r['identity'], r['revision'])
                  for r in self.w.h.get(self.w.constraints).payload['allowed_action_refs']))

    def install(self):
        return RestrictedEntry(self.w.runtime, self.profile)

    def candidate(self):
        adapter = DeepSeekAdapter(LLMConfig('LOCAL-ONLY', base_url=self.w.endpoint, max_calls=4), local_transport)
        return self.w.generate_and_validate(adapter, self.w.turn, self.w.context)

    def test_permitted_hint_runs_through_formal_commit_and_dispatch(self):
        self.install(); candidate, review = self.candidate()
        outcome = self.w.commit_and_record(self.w.turn, candidate, review)
        self.assertEqual(outcome.status, 'Committed')
        self.w.allow_reads()
        intent = self.w.actions.create_intent(self.w.tokens['interaction'], candidate.record.ref,
            expires_at=self.w.h.clock.now+100, idempotency_key='allowed')
        self.w.sessions.bind_intent(self.w.turn, intent)
        result = self.w.actions.execute(self.w.tokens['interaction'], intent)
        self.assertEqual(self.w.h.get(result).payload['status'], 'Occurred')
        self.w.sessions.effect_result(self.w.turn, result); self.w.sessions.settle(self.w.turn)

    def test_pre_scope_candidate_cannot_commit_forbidden_action(self):
        candidate, review = self.candidate()
        forbidden = next(r for r in self.w.action_refs if r not in self.profile.actions)
        action = self.w.h.get(forbidden)
        payload = {**candidate.record.payload, 'action_identity':forbidden.identity,
                   'action_revision':forbidden.revision, 'exact_payload':action.payload['exact_payload']}
        candidate = self.w.runtime.propose(self.w.context, 'P-forbidden', 'r1', payload)
        review = self.w.runtime.record_semantic_validation(self.w.tokens['interaction'], candidate,
            'PASS', 'Scripted cannot override scope', 'LOCAL', fixture=True)
        self.install()
        outcome = self.w.runtime.commit(self.w.tokens['interaction'], candidate, review.identity)
        self.assertEqual((outcome.status, outcome.reason), ('ValidationFailed', 'WorkingActionOutsideScope'))
        self.assertIsNone(self.w.h.get(candidate.record.ref))

    def test_wrong_protocol_and_envelope_cannot_reach_generation(self):
        entry = self.install()
        for context, reason in [
            (replace(self.w.context, protocol=self.w.protocol.ref), 'WorkingProtocolOutsideScope'),
            (replace(self.w.context, items=tuple(i for i in self.w.context.items if i.record.ref != self.w.constraints)), 'WorkingActivityEnvelopeMismatch')]:
            self.w.runtime._contexts[context.identity] = context
            with self.assertRaisesRegex(ContractError, reason): entry.check_context(context)
        self.w.runtime._contexts[self.w.context.identity] = self.w.context

    def test_missing_or_replaced_serial_session_is_rejected(self):
        self.install(); self.w.runtime.session = None
        with self.assertRaisesRegex(ContractError, 'WorkingSerialSessionRequired'):
            self.w.runtime.check_turn(self.w.context)

    def test_unbound_context_cannot_escape_serial_turn(self):
        entry = self.install()
        context = replace(self.w.context, identity='unbound', items=tuple(
            i for i in self.w.context.items if i.record.kind != 'CurrentInteractionInput'))
        self.w.runtime._contexts[context.identity] = context
        with self.assertRaisesRegex(ContractError, 'WorkingTurnBindingRequired'): entry.check_context(context)

    def test_scope_registration_is_immutable(self):
        self.install()
        with self.assertRaisesRegex(ContractError, 'WorkingScopeAlreadyRegistered'): self.install()

    def test_transition_cannot_be_declared_as_allowed_local_action(self):
        ref = seed(self.w.h, Ref(Space.CANONICAL, 'forbidden-control', 'v1'), kind='ActionSemantic',
                   payload={'executor_target':'activity-control','exact_payload':'switch'})
        with self.assertRaisesRegex(ContractError, 'WorkingLocalActionRequired'):
            RestrictedEntry(self.w.runtime, replace(self.profile, actions=self.profile.actions+(ref,)))
        self.assertIsNone(self.w.runtime.working_entry)

    def test_pre_existing_control_intent_cannot_dispatch_after_scope_install(self):
        from test_activity_composition import LocalWorld, transport
        from run_activity_composition_validation import execute_path
        row, snapshots = execute_path(self.e, 1, LLMConfig('LOCAL-ONLY',
            base_url='https://api.deepseek.com/beta', max_calls=24), transport, LocalWorld)
        self.assertEqual(row['result'], 'PASS')
        world = snapshots['switch-teaching']
        world.e = self.e
        hint = world.register_action('WorkingHint', 'Check the visible calculation.', disclosure='LOCAL_HINT')
        envelope = seed(world.h, Ref(Space.CANONICAL, 'WorkingActivityEnvelope', 'v1'),
            kind='ActivityConstraints', payload={'episode':world.episode, 'allowed_action_refs':[json_value(hint)]})
        profile = WorkingScope('FixedActivityEntry', 'v1', 'learner-A', 'learner-A', 'learning',
            (world.protocols['policy'].ref,), envelope, (hint,))
        original = world.h.get(world.current_intent)
        self.assertEqual(original.payload['executor_target'], 'activity-control')
        RestrictedEntry(world.runtime, profile)
        result = world.control.execute(world.tokens['interaction'], world.current_intent)
        self.assertEqual((world.h.get(result).payload['status'], world.h.get(result).payload['reason']),
                         ('NotOccurred', 'WorkingActionOutsideScope'))
        self.assertEqual(world.h.get(world.activity).payload['activity_purpose'], 'IndependentDiagnosis')
        self.assertEqual(world.h.get(world.current_intent), original)
        self.assertFalse(any(r.kind == 'ActivityTransitionOccurred' for r in world.h.facts.records()))

    def test_entry_creates_serial_coordinator_if_none_exists(self):
        self.w.runtime.session = None
        entry = self.install()
        self.assertIs(self.w.runtime.session, entry.session)
        with self.assertRaisesRegex(ContractError, 'WorkingTurnBindingRequired'):
            self.w.runtime.check_turn(self.w.context)

    def test_queued_and_closed_turn_remain_blocked(self):
        self.install(); self.w.queue_second()
        with self.assertRaisesRegex(ContractError, 'ConversationTurnActive'): self.w.sessions.start('C')
        failure = self.w.runtime.execution('TurnFailure', 'learner-A', {'turn_ref':json_value(self.w.turn)})
        self.w.sessions.begin_close(self.w.turn, failure)
        with self.assertRaisesRegex(ContractError, 'TurnClosed'): self.w.runtime.check_turn(self.w.context)
        self.w.sessions.finish_close(self.w.turn)
        self.assertEqual(self.w.sessions.turns[self.w.sessions.start('C')]['input'], self.w.second_input)

    def test_independent_evaluation_owner_remains_available(self):
        self.install()
        self.assertIsNotNone(self.w.external_update())
