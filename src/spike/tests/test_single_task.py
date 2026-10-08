"""M1-M7: controlled mechanics and message boundaries; no semantic evidence."""
import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from foundation.boundary import ContextItem
from foundation.cases import EvidenceRecorder, correct, seed
from foundation.llm import DeepSeekAdapter, LLMConfig, ModelFailure
from foundation.records import Ref, Space, json_value
from foundation.runtime import ContractError, Decision
from foundation.security import DataUse, Operation, parameter
from foundation.single_task import (CallBudget, RECEIPTS, SingleTaskWorld,
                                    load_plan, run_batch)


class ScriptedTransport:
    """Responses chosen by explicit test controls, never by language heuristics."""
    def __init__(self):
        self.outcome = 'HintCheckStep'
        self.fail_calls = set()
        self.calls = []
        self.timeouts = []
        self.callback = None
        self.policy_changes = {}
        self.policy_status = 'PASS'

    def before_turn(self, spec, number):
        self.outcome = spec['scripted_mechanical_outcomes'][number - 1]

    def __call__(self, url, key, wire, timeout):
        self.calls.append(wire)
        self.timeouts.append(timeout)
        if self.callback:
            callback, self.callback = self.callback, None
            callback()
        if len(self.calls) in self.fail_calls:
            raise TimeoutError('Controlled offline failure')
        contract = wire['tools'][0]['function']
        name = contract['name']
        body = json.loads(wire['messages'][1]['content'])
        if name == 'submit_observation':
            value = {'description': 'A scripted local observation for mechanism checks.'}
        elif name == 'submit_responsibility':
            value = {'segments': [{'field': 'description', 'text': body['candidate']['description'],
                                  'role': 'local_observation', 'rationale': 'Scripted.'}]}
        elif name == 'submit_extraction':
            value = {'segments': [{'field': 'description', 'text': body['candidate']['description'],
                                  'coverage': 'COMPLETE', 'expressions': []}]}
        elif name == 'submit_policy':
            received = next(x for x in body if x['kind'] == 'CurrentInteractionInput')
            constraints = next(x for x in body if x['kind'] == 'ActivityConstraints')
            execute = self.outcome not in ('NoIntervention', 'Defer')
            action = next((x for x in body if x['kind'] == 'ActionSemantic'
                           and x['ref']['identity'] == self.outcome), None)
            value = {'outcome': 'Execute' if execute else self.outcome,
                     'action_identity': self.outcome if execute else '',
                     'action_revision': 'e1-v1' if execute else '',
                     'exact_payload': action['content']['exact_payload'] if action else '',
                     'executor_target': 'mock-display' if execute else '',
                     'episode': constraints['content']['episode'],
                     'context_refs': [received['ref']],
                     'rationale': 'AUDIT_POLICY_SENTINEL Scripted rationale.',
                     'expected_disclosure': 'AUDIT_EXPECTED_SENTINEL This is only a proposal.',
                     'uncertainty': 'Scripted mechanics do not establish quality.',
                     'defer_condition': 'A new learner work submission.' if self.outcome == 'Defer' else ''}
            value.update(self.policy_changes)
        elif set(contract['parameters']['properties']) == {'status', 'rationale'}:
            value = {'status': self.policy_status, 'rationale': 'AUDIT_REVIEW_SENTINEL Scripted.'}
        else:
            text = body['candidate']['description']
            props = contract['parameters']['properties']
            criteria = props['criteria']['items']['properties']['id']['enum']
            sources = props['claims']['items']['properties']['sources']['items']['enum']
            value = {'reviewed_fields': ['description'],
                     'criteria': [{'id': c, 'status': 'PASS',
                         'quotes': [{'field': 'description', 'text': text}], 'rationale': 'Scripted.'}
                                  for c in criteria],
                     'claims': [{'field': 'description', 'text': text, 'kind': 'paraphrase',
                         'reported_quote': None, 'status': 'PASS', 'sources': [sources[0]],
                         'rationale': 'Scripted.', 'support': 'supported',
                         'attribution': {'speaker': 'system', 'stance': 'endorsed'},
                         'boundary_status': 'PASS', 'inspection_scope': 'COMPLETE_CONTEXT'}]}
        return {'choices': [{'finish_reason': 'tool_calls', 'message': {'content': None,
            'tool_calls': [{'id': 'scripted', 'type': 'function', 'function': {'name': name,
                'arguments': json.dumps(value, ensure_ascii=False)}}]}}]}


class SingleTaskTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.plan = load_plan()
        self.transport = ScriptedTransport()
        self.adapter = DeepSeekAdapter(LLMConfig('OFFLINE-ONLY', base_url=self.plan['model']['base_url'],
            max_calls=168, max_output_tokens=4096), self.transport)
        self.e = EvidenceRecorder(self.directory / 'test.jsonl')
        self.addCleanup(self.e.close)
        self.w = SingleTaskWorld(self.e, 'test', self.plan)

    def begin(self):
        self.w.receive(self.plan['sessions'][2]['inputs'][0])
        self.w.start()
        return self.w.context('work')

    def observation(self):
        context = self.begin()
        row = {}
        candidate = self.w.runtime.generate_with_llm(self.w.token, context, self.adapter,
                                                   identity=self.w.identity('work', 1))
        review = self.w.runtime.validate_with_llm(self.w.token, candidate, self.adapter)
        return candidate, review

    def process(self, **kwargs):
        self.w.receive(self.plan['sessions'][2]['inputs'][0])
        return self.w.process(self.adapter, **kwargs)

    def test_M1_required_review_status_digest_and_rule(self):
        candidate, review = self.observation()
        variants = [('missing', None)]
        for changes in ({'status': 'FAIL'}, {'status': 'UNRESOLVED'},
                        {'candidate_digest': 'wrong'},
                        {'rule': Ref(Space.CANONICAL, review.rule.identity, 'old')}):
            altered = replace(review, identity='altered-' + str(len(variants)), **changes)
            self.w.runtime._reviews[altered.identity] = altered
            variants.append((altered.identity, altered))
        for identity, _ in variants:
            with self.subTest(review=identity):
                outcome = self.w.runtime.commit(self.w.token, candidate, identity)
                self.assertNotEqual(outcome.status, 'Committed')
                self.assertIsNone(self.w.h.get(candidate.record.ref))
        self.assertEqual(self.w.runtime.commit(self.w.token, candidate, review.identity).status, 'Committed')

    def test_M1_invalidated_source_is_rejected(self):
        candidate, review = self.observation()
        correct(self.w.h, self.w.work)
        outcome = self.w.runtime.commit(self.w.token, candidate, review.identity)
        self.assertNotEqual(outcome.status, 'Committed')
        self.assertIsNone(self.w.h.get(candidate.record.ref))

    def test_M2_no_evaluation_capability_and_no_scripted_states(self):
        self.assertEqual(self.w.h.states.records(), ())
        for kind in ('Evidence', 'LearnerBelief'):
            request = Operation('learning', 'learner-A', self.w.identity('work', 1), 'commit',
                                (parameter('owner', 'Evaluation'), parameter('kind', kind)))
            self.assertEqual(self.w.security.authority(self.w.token, request).decision, Decision.DENY)
            self.assertEqual(self.w.security.data_authority(self.w.token,
                DataUse('learning', 'learner-A', kind, 'commit', 'formal-state')).decision, Decision.DENY)
        self.assertTrue(all(p.owner == 'Interaction' for p in self.w.runtime._protocols.values()))

    def test_M2_forged_owner_is_rejected(self):
        candidate, review = self.observation()
        changed = replace(candidate, record=replace(candidate.record, owner='Evaluation'))
        self.w.runtime._candidates[changed.identity] = changed
        outcome = self.w.runtime.commit(self.w.token, changed, review.identity)
        self.assertEqual(outcome.reason, 'CandidateStandingMismatch')

    def test_M2_wrong_task_and_conversation_before_model_call(self):
        for kwargs in ({'conversation': 'other'}, {'task': 'different-task'}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ContractError, 'InputScopeMismatch'):
                self.w.receive('input', **kwargs)
        self.assertEqual(self.adapter.calls, 0)
        self.assertFalse(self.w.received)

    def test_M2_forbidden_action_or_payload_never_displayed(self):
        for changes in ({'action_identity': 'RevealFullSolution'}, {'exact_payload': 'The answer is 105.'}):
            with self.subTest(changes=changes):
                evidence = EvidenceRecorder(self.directory / ('negative-' + str(len(changes)) + uuid_suffix(changes) + '.jsonl'))
                self.addCleanup(evidence.close)
                world = SingleTaskWorld(evidence, 'negative', self.plan)
                self.transport.policy_changes = changes
                world.receive('A submitted work input.')
                row = world.process(self.adapter)
                self.assertEqual(row['execution'], 'FAILED')
                self.assertEqual(row['displayed'], [])
                self.assertFalse(any(r.kind == 'ActionIntent' for r in world.h.executions.records()))

    def test_M3_prior_policy_and_reviewer_are_absent_from_next_messages(self):
        first = self.process()
        self.assertEqual(first['execution'], 'COMPLETED')
        start = len(self.adapter.records)
        self.transport.outcome = 'NoIntervention'
        self.w.receive(self.plan['sessions'][2]['inputs'][1])
        second = self.w.process(self.adapter)
        self.assertEqual(second['execution'], 'COMPLETED')
        for record in self.adapter.records[start:]:
            body = json.loads(record['messages'][1]['content'])
            context = body if isinstance(body, list) else body.get('context', [])
            text = json.dumps(context)
            self.assertNotIn('AUDIT_POLICY_SENTINEL', text)
            self.assertNotIn('AUDIT_REVIEW_SENTINEL', text)
            self.assertNotIn('AUDIT_EXPECTED_SENTINEL', text)
            self.assertTrue(any(x['kind'] == 'AssistanceContext' for x in context))
            self.assertTrue(any(x['kind'] == 'LearnerWorkSubmitted' for x in context))
            self.assertNotIn('author_acceptance', text)

    def test_M3_assembled_extra_source_cannot_enter_generation(self):
        context = self.begin()
        extra = seed(self.w.h, Ref(Space.FACT, 'alien', '1'), kind='LearnerWorkSubmitted',
                     payload={'text': 'audit-only', 'conversation': 'other'})
        mutated = replace(context, items=context.items + (ContextItem(self.w.h.get(extra), (), ()),))
        self.w.runtime._contexts[context.identity] = mutated
        with self.assertRaisesRegex(ContractError, 'SourceContractMismatch'):
            self.w.runtime.generate_with_llm(self.w.token, mutated, self.adapter)
        self.assertEqual(self.adapter.calls, 0)

    def test_M3_failed_observation_does_not_generate_policy_or_enter_next_turn(self):
        self.transport.fail_calls = {2}
        first = self.process()
        self.assertEqual(first['execution'], 'FAILED')
        self.assertEqual(self.adapter.calls, 2)
        self.assertFalse(self.w.h.states.records())
        self.transport.outcome = 'NoIntervention'
        self.w.receive('42 / 6 = 7; 7 * 15 = 105.')
        second = self.w.process(self.adapter)
        self.assertEqual(second['execution'], 'COMPLETED')
        self.assertEqual(second['assistance']['exposures'], [])
        self.assertEqual(len(self.w.h.states.records()), 2)

    def test_M4_full_partial_none_and_unknown_help(self):
        for mode in ('OCCUR_FULL', 'OCCUR_PARTIAL', 'NOT_OCCURRED', 'INDETERMINATE'):
            with self.subTest(mode=mode):
                evidence = EvidenceRecorder(self.directory / (mode + '.jsonl'))
                self.addCleanup(evidence.close)
                world = SingleTaskWorld(evidence, mode, self.plan)
                world.receive('Submitted work.')
                first = world.process(self.adapter, effect_mode=mode,
                                      partial_characters=3 if mode == 'OCCUR_PARTIAL' else None)
                world.receive('Next work.')
                world.start()
                history = world.help_views[world.help]
                self.assertEqual(history['learner_used_assistance'], 'NOT_INFERRED')
                if mode in ('OCCUR_FULL', 'OCCUR_PARTIAL'):
                    self.assertEqual(len(history['exposures']), 1)
                    actual = history['exposures'][0]
                    self.assertEqual(actual['completeness'], 'FULL' if mode == 'OCCUR_FULL' else 'PARTIAL')
                    self.assertEqual(actual['payload'], self.plan['actions']['HintCheckStep'] if mode == 'OCCUR_FULL'
                                     else self.plan['actions']['HintCheckStep'][:3])
                    self.assertTrue(actual['before_response'])
                else:
                    self.assertEqual(history['exposures'], [])
                    self.assertEqual(history['unconfirmed'][0]['status'],
                                     'NotOccurred' if mode == 'NOT_OCCURRED' else 'Indeterminate')
                self.assertEqual(first['execution'], 'COMPLETED' if mode == 'OCCUR_FULL' else 'FAILED')

    def test_M5_queue_during_understanding_does_not_start(self):
        def interrupt():
            self.w.receive('Second queued input.')
            with self.assertRaisesRegex(ContractError, 'ConversationTurnActive'):
                self.w.start()
            self.assertEqual(self.adapter.calls, 1)
        self.transport.callback = interrupt
        first = self.process()
        self.assertEqual(first['execution'], 'COMPLETED')
        self.transport.outcome = 'NoIntervention'
        second = self.w.process(self.adapter)
        self.assertEqual(second['execution'], 'COMPLETED')
        self.assertFalse(second['assistance']['exposures'][0]['before_response'])

    def test_M5_closed_turn_discards_late_generation(self):
        self.transport.callback = lambda: self.w.close_failure('UserInterrupted')
        first = self.process()
        self.assertEqual(first['execution'], 'FAILED')
        self.assertFalse(self.w.h.states.records())
        self.assertEqual(self.adapter.calls, 1)
        self.assertTrue(any(r.kind == 'LateGenerationDiscarded' for r in self.w.h.executions.records()))
        self.w.receive('Next input after interruption.')
        self.assertEqual(self.w.process(self.adapter)['execution'], 'COMPLETED')

    def test_M5_unknown_inflight_effect_does_not_release_queue(self):
        def timeout(token, intent, **kwargs):
            self.w.sessions.before_effect(intent)
            raise ModelFailure('ControlledEffectTimeout')
        self.w.actions.execute = timeout
        first = self.process()
        self.assertTrue(first['session_blocked'])
        self.assertEqual(first['receipt'], RECEIPTS['BLOCKED'])
        self.w.receive('Pending next work.')
        calls = self.adapter.calls
        with self.assertRaisesRegex(ContractError, 'ConversationTurnActive'):
            self.w.process(self.adapter)
        self.assertEqual(self.adapter.calls, calls)
        self.assertFalse(any(r.kind == 'ActionExecutionResult' for r in self.w.h.executions.records()))

    def test_M5_rejected_policy_cannot_be_dispatched_later(self):
        self.transport.policy_status = 'FAIL'
        first = self.process()
        self.assertEqual(first['execution'], 'FAILED')
        policy = next(c for c in self.w.runtime._candidates.values() if c.record.kind == 'PolicyOutcome')
        with self.assertRaisesRegex(ContractError, 'CommittedPolicyRequired'):
            self.w.actions.create_intent(self.w.token, policy.record.ref,
                                        expires_at=100000, idempotency_key='late')

    def test_M5_input_at_commit_is_queued_and_closed_policy_stays_closed(self):
        candidate, review = self.observation()
        self.w.receive('Arrived while commit was pending.')
        with self.assertRaisesRegex(ContractError, 'ConversationTurnActive'):
            self.w.start()
        self.w.close_failure('InterruptedBeforeCommit')
        outcome = self.w.runtime.commit(self.w.token, candidate, review.identity)
        self.assertNotEqual(outcome.status, 'Committed')
        self.assertIsNone(self.w.h.get(candidate.record.ref))
        self.assertEqual(self.w.process(self.adapter)['execution'], 'COMPLETED')

    def test_M6_no_intervention_defer_and_failure_receipts(self):
        for choice in ('NoIntervention', 'Defer'):
            with self.subTest(choice=choice):
                self.transport.outcome = choice
                self.w.receive('Work input.')
                row = self.w.process(self.adapter)
                self.assertEqual(row['execution'], 'COMPLETED')
                self.assertEqual(row['receipt'], RECEIPTS[choice])
                self.assertEqual(row['displayed'], [])
        self.assertFalse(any(r.kind == 'ActionIntent' for r in self.w.h.executions.records()))

    def batch(self, **kwargs):
        return run_batch(self.plan, self.adapter,
            lambda name: EvidenceRecorder(self.directory / (name + '.jsonl')),
            before_turn=self.transport.before_turn, **kwargs)

    def test_M7_all_fixed_sessions_have_two_turns_and_no_utility_calls(self):
        result = self.batch()
        self.assertIsNone(result['stop_reason'])
        self.assertEqual([r['execution'] for r in result['rows']], ['COMPLETED'] * 12)
        self.assertEqual(result['calls'], 144)
        self.assertFalse(any(c['purpose'] == 'PolicyUtilityReview' for c in self.adapter.records))
        self.assertTrue(all('scripted_mechanical_outcomes' not in json.dumps(c['messages'])
                            for c in self.adapter.records))

    def test_M7_normal_failure_does_not_stop_other_turns_or_sessions(self):
        self.transport.fail_calls = {1}
        result = self.batch()
        self.assertIsNone(result['stop_reason'])
        self.assertEqual(result['rows'][0]['turns'][0]['execution'], 'FAILED')
        self.assertEqual(result['rows'][0]['turns'][1]['execution'], 'COMPLETED')
        self.assertEqual([r['execution'] for r in result['rows'][1:]], ['COMPLETED'] * 11)
        self.assertEqual(result['calls'], 139)

    def test_M7_call_budget_stops_without_replacement(self):
        self.plan['budget']['max_calls'] = 1
        result = self.batch()
        self.assertEqual(result['calls'], 1)
        self.assertEqual(result['stop_reason'], 'BudgetExhausted')
        self.assertEqual(sum(t['execution'] == 'NOT_RUN' for r in result['rows'] for t in r['turns']), 23)

    def test_M7_deadline_stops_before_transport(self):
        result = self.batch(clock=iter([0] + [3000] * 30).__next__)
        self.assertEqual(result['calls'], 0)
        self.assertEqual(result['stop_reason'], 'BudgetExhausted')
        self.assertEqual(sum(t['execution'] == 'NOT_RUN' for r in result['rows'] for t in r['turns']), 24)

    def test_M7_timeout_is_capped_and_late_reply_not_committed(self):
        now = [0]
        self.plan['budget']['wall_time_seconds'] = 5
        self.transport.callback = lambda: now.__setitem__(0, 6)
        result = self.batch(clock=lambda: now[0])
        self.assertEqual(self.transport.timeouts, [5])
        self.assertEqual(result['calls'], 1)
        self.assertEqual(result['stop_reason'], 'BudgetExhausted')
        self.assertIn('DeadlineReachedAfterCall', result['rows'][0]['turns'][0]['reason'])
        self.assertNotIn('work_commit', result['rows'][0]['turns'][0])

    def test_M7_semantic_fail_is_recorded_without_stopping_other_sessions(self):
        self.transport.policy_status = 'FAIL'
        result = self.batch()
        self.assertIsNone(result['stop_reason'])
        self.assertEqual(result['calls'], 144)
        for row in result['rows']:
            self.assertEqual(row['execution'], 'FAILED')
            for turn in row['turns']:
                self.assertEqual(turn['displayed'], [])
                self.assertEqual(turn['policy_review']['status'], 'FAIL')
                self.assertEqual(turn['receipt'], RECEIPTS['FAILED'])


def uuid_suffix(value):
    return '-payload' if 'exact_payload' in value else '-action'


if __name__ == '__main__':
    unittest.main()
