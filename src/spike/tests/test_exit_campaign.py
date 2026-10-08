"""Finite execution and actual boundary integration; scripted judgments are not semantic tests."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from foundation.cases import EvidenceRecorder
from foundation.exit_campaign import CONFIG, ExitBudget, audit_messages, read, run_schedule
from foundation.llm import DeepSeekAdapter, LLMConfig
from foundation.runtime import ContractError
from foundation.boundary import digest
from foundation.guarded_cases import setup_boundary
from foundation.records import Ref, Space
from dataclasses import replace
from prepare_spike_exit import ScriptedTransport, ExactReplay, preflight


class ExitCampaignTests(unittest.TestCase):
    artifact_directory = None
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.plan = read('src/spike/fixtures/spike-exit-v1.json')
        self.plan['schedule'] = self.plan['schedule'][:2]
        self.transport = ScriptedTransport()
        self.adapter = DeepSeekAdapter(LLMConfig('OFFLINE-ONLY', base_url='https://api.deepseek.com/beta',
            max_calls=375, max_output_tokens=4096), self.transport)

    def run_cases(self, **kwargs):
        return run_schedule(self.plan, self.adapter, lambda id: EvidenceRecorder(self.folder / (id + '.jsonl')),
            before_case=self.transport.before_case, **kwargs)

    def test_target_false_pass_stops_before_scoring_review_or_next_case(self):
        original = self.transport.before_case
        def force(spec):
            original({**spec, 'expected_semantic': 'PASS'})
        self.transport.before_case = force
        reviews = []
        result = self.run_cases(content_review=lambda *a: reviews.append(a))
        self.assertEqual(result['rows'][0]['execution'], 'FAILED')
        self.assertEqual(result['rows'][1]['execution'], 'NOT_RUN')
        self.assertEqual(self.adapter.calls, 1)
        self.assertEqual(reviews, [])

    def test_transport_failure_stops_without_retry_or_replacement(self):
        calls = []
        def broken(*args):
            calls.append(1)
            raise TimeoutError()
        self.adapter.transport = broken
        result = self.run_cases(content_review=lambda *a: True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.adapter.calls, 1)
        self.assertEqual(result['rows'][1]['execution'], 'NOT_RUN')

    def test_missing_author_review_cannot_advance_on_model_scores(self):
        result = self.run_cases()
        self.assertEqual(self.adapter.calls, 2)
        self.assertIn('ContentReviewNotAccepted', result['stop_reason'])
        self.assertEqual(result['rows'][1]['execution'], 'NOT_RUN')

    def test_declared_positive_and_negative_controls_use_v5_and_isolated_labels(self):
        result = self.run_cases(content_review=lambda *a: True)
        self.assertIsNone(result['stop_reason'])
        self.assertEqual(self.adapter.calls, 4)
        self.assertEqual([r['semantic_status'] for r in result['rows']], ['FAIL', 'PASS'])
        for record in self.adapter.records:
            audit_messages(record['messages'])
        wire = self.adapter.records[0]
        quote = wire['output_contract']['parameters']['properties']['findings']['items']['properties']['candidate_quotes']['items']
        self.assertEqual(set(quote['properties']), {'handle'})

    def test_per_case_limit_prevents_a_second_call(self):
        self.plan['schedule'][0]['max_calls'] = 1
        result = self.run_cases(content_review=lambda *a: True)
        self.assertEqual(self.adapter.calls, 1)
        self.assertIn('WorkingCallBudgetExhausted', result['stop_reason'])

    def test_deadline_prevents_first_call(self):
        result = self.run_cases(content_review=lambda *a: True, clock=iter([0, 3601]).__next__)
        self.assertEqual(self.adapter.calls, 0)
        self.assertIn('WorkingDeadlineExhausted', result['stop_reason'])

    def test_last_timeout_capped_and_late_return_cannot_start_next_call(self):
        timeouts = []
        original = self.adapter.transport
        def capture(url, key, wire, timeout):
            timeouts.append(timeout)
            return original(url, key, wire, timeout)
        self.adapter.transport = capture
        result = self.run_cases(content_review=lambda *a: True, clock=iter([0, 3599, 3601]).__next__)
        self.assertEqual(timeouts, [1])
        self.assertEqual(self.adapter.calls, 1)
        self.assertIn('WorkingDeadlineReachedAfterCall', result['stop_reason'])

    def test_host_labels_rejected_before_transport(self):
        budget = ExitBudget(self.adapter, self.plan['budget'])
        budget.begin_case(1)
        with self.assertRaisesRegex(ContractError, 'ExitHostLabelsInRequest'):
            budget.complete([{'role': 'user', 'content': json.dumps({'expected_semantic': 'PASS'})}], 'test')
        self.assertEqual(self.adapter.calls, 0)

    def test_x5_schema_extension_preserves_semantic_system_and_review_contract(self):
        plan = read('src/spike/fixtures/spike-exit-v1.json')
        preflight(plan)
        e1 = read(plan['protocols']['policy'])
        x5 = read(plan['protocols']['x5_policy'])
        for key in ('validation_system', 'generation_system', 'validation_format', 'semantic_rules'):
            self.assertEqual(e1.get(key), x5.get(key))
        self.assertEqual(e1['output_contracts']['validation'], x5['output_contracts']['validation'])
        self.assertIn('activity-control', x5['output_contracts']['generation']['parameters']['properties']['executor_target']['enum'])
        self.assertNotIn('activity-control', e1['output_contracts']['generation']['parameters']['properties']['executor_target']['enum'])

    def test_historical_mapping_cannot_change_semantic_source_content(self):
        file = self.folder / 'old.jsonl'
        prior = {'ref': {'space': 'fact', 'identity': '1' * 32, 'revision': '1'}, 'kind': 'ActionOccurrence',
                 'content': {'actual_disclosure': {'rendered_at': 38, 'payload': 'actual cue'}}}
        messages = [{'role': 'system', 'content': 'same'}, {'role': 'user', 'content': json.dumps([prior])}]
        file.write_text(json.dumps({'kind': 'model_execution', 'messages': messages}), encoding='utf-8')
        replay = ExactReplay(file)
        now = deepcopy(prior)
        now['ref']['identity'] = '2' * 32
        now['content']['actual_disclosure']['rendered_at'] = 40
        current = [messages[0], {'role': 'user', 'content': json.dumps([now])}]
        mapped = replay.mapped_messages(messages, current)
        self.assertEqual(json.loads(mapped[1]['content']), [now])
        now['content']['actual_disclosure']['payload'] = 'different cue'
        current[1]['content'] = json.dumps([now])
        mapped = replay.mapped_messages(messages, current)
        self.assertNotEqual(json.loads(mapped[1]['content']), [now])

    def test_observation_wrong_rule_or_context_cannot_commit(self):
        folder = self.artifact_directory or self.folder
        e = EvidenceRecorder(folder / (self._testMethodName + '.jsonl'))
        try:
            for field, value in [('rule', Ref(Space.CANONICAL, 'WrongRule', 'v1')), ('context_id', 'different-context')]:
                h, s, r, token, ctx, candidate, review = setup_boundary()
                r._reviews[review.identity] = replace(review, **{field: value})
                outcome = r.commit(token, candidate, review.identity)
                e.emit('binding_failure_injection', changed_field=field, candidate_digest=digest(candidate),
                       outcome=outcome.reason, review_ref=review.identity)
                self.assertEqual(outcome.reason, 'SemanticValidationBindingMismatch')
                self.assertIsNone(h.get(candidate.record.ref))
                e.capture(h, field + ':final')
        finally:
            e.close()

    def test_untrusted_validation_execution_cannot_grant_standing(self):
        folder = self.artifact_directory or self.folder
        e = EvidenceRecorder(folder / (self._testMethodName + '.jsonl'))
        try:
            h, s, r, token, ctx, candidate, review = setup_boundary()
            fake = r.execution('UntrustedSelfAttestation', 'learner-A',
                               {'candidate_digest': digest(candidate), 'status': 'PASS'})
            r._reviews[review.identity] = replace(review, execution=fake)
            outcome = r.commit(token, candidate, review.identity)
            self.assertEqual(outcome.reason, 'UntrustedValidationExecution')
            self.assertIsNone(h.get(candidate.record.ref))
            e.emit('untrusted_record_failure_injection', outcome=outcome.reason)
            e.capture(h, 'final')
        finally:
            e.close()


if __name__ == '__main__':
    unittest.main()
