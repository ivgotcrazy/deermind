"""Diagnostic execution safeguards; canned outputs do not test semantic quality."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from foundation.llm import DeepSeekAdapter, LLMConfig
from foundation.s3_diagnostic import audit_request, build_plan, object_hash, run_plan, write
import run_policy_s3_diagnostic as runner


class Clock:
    value = 0
    def __call__(self):
        return self.value


class S3DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_plan()
        self.clock = Clock()
        self.outputs = [{'action_meaning': 'canned action judgment',
            'rationale_claim': 'canned rationale judgment', 'reason': 'canned basis',
            'status': spec['expected_status']} for spec in self.plan['schedule']]
        self.wires = []
        self.adapter = DeepSeekAdapter(LLMConfig('OFFLINE-ONLY',
            base_url='https://api.deepseek.com/beta', max_calls=12), self.transport)

    def transport(self, url, key, payload, timeout):
        self.wires.append((payload, timeout))
        output = self.outputs[len(self.wires)-1]
        return {'model': 'deepseek-flash', 'choices': [{'finish_reason': 'tool_calls',
            'message': {'content': None, 'tool_calls': [{'type': 'function',
                'function': {'name': 'submit_review', 'arguments': json.dumps(output)}}]}}]}

    def run_cases(self, **kwargs):
        return run_plan(self.plan, self.adapter, clock=self.clock, **kwargs)

    def test_twelve_calls_and_candidate_changes_only_in_rationale(self):
        result = self.run_cases(review=lambda *args: True)
        self.assertIsNone(result['stop_reason'])
        self.assertEqual(self.adapter.calls, 12)
        self.assertTrue(all(r['execution'] == 'COMPLETED' for r in result['rows']))
        baseline = json.loads(self.plan['schedule'][0]['messages'][1]['content'])
        baseline['candidate'].pop('rationale')
        for wire, timeout in self.wires:
            payload = audit_request(wire['messages'])
            payload['candidate'].pop('rationale')
            self.assertEqual(payload, baseline)
            self.assertEqual(timeout, 60)

    def test_host_label_rejected_before_transport(self):
        spec = self.plan['schedule'][0]
        payload = json.loads(spec['messages'][1]['content'])
        payload['expected_status'] = 'FAIL'
        spec['messages'][1]['content'] = json.dumps(payload)
        result = self.run_cases(review=lambda *args: True)
        self.assertEqual(self.adapter.calls, 0)
        self.assertIn('HostLabels', result['stop_reason'])

    def test_changed_request_rejected_before_transport(self):
        spec = self.plan['schedule'][0]
        spec['messages'][0]['content'] += ' changed'
        result = self.run_cases(review=lambda *args: True)
        self.assertEqual(self.adapter.calls, 0)
        self.assertIn('RequestBinding', result['stop_reason'])

    def test_wrong_status_stops_without_next_call(self):
        self.outputs[0]['status'] = 'PASS'
        reviews = []
        result = self.run_cases(review=lambda *args: reviews.append(args))
        self.assertEqual(self.adapter.calls, 1)
        self.assertEqual(reviews, [])
        self.assertEqual(sum(r['execution'] == 'NOT_RUN' for r in result['rows']), 11)

    def test_correct_status_but_author_rejects_meaning_stops(self):
        result = self.run_cases(review=lambda *args: False)
        self.assertEqual(self.adapter.calls, 1)
        self.assertIn('AuthorReview', result['stop_reason'])

    def test_missing_review_does_not_advance(self):
        result = self.run_cases()
        self.assertEqual(self.adapter.calls, 1)
        self.assertIn('AuthorReview', result['stop_reason'])

    def test_transport_failure_persisted_and_never_retried(self):
        attempts, saves = [], {}
        def failure(*args):
            attempts.append(1)
            raise TimeoutError()
        self.adapter.transport = failure
        result = self.run_cases(review=lambda *args: True,
            save=lambda name, value: saves.update({name: deepcopy(value)}))
        self.assertEqual(attempts, [1])
        self.assertEqual(saves['adapter-records.json'][0]['failure'], 'ProviderTimeout')
        self.assertIn('ProviderTimeout', result['stop_reason'])

    def test_nonempty_judgments_required_even_if_status_matches(self):
        self.outputs[0]['rationale_claim'] = ' '
        result = self.run_cases(review=lambda *args: True)
        self.assertEqual(self.adapter.calls, 1)
        self.assertIn('EmptyJudgment', result['stop_reason'])

    def test_deadline_before_call_and_global_call_cap(self):
        self.clock.value = 901
        result = self.run_cases(review=lambda *args: True, deadline=900)
        self.assertEqual(self.adapter.calls, 0)
        self.assertIn('DeadlineBeforeCall', result['stop_reason'])
        self.clock.value = 0
        self.plan['max_calls'] = 1
        result = self.run_cases(review=lambda *args: True)
        self.assertEqual(self.adapter.calls, 1)
        self.assertIn('CallBudget', result['stop_reason'])

    def test_timeout_capped_and_late_return_stops_before_review(self):
        self.clock.value = 899
        original = self.adapter.transport
        def late(*args):
            output = original(*args)
            self.clock.value = 901
            return output
        self.adapter.transport = late
        reviews = []
        result = self.run_cases(review=lambda *args: reviews.append(args), deadline=900)
        self.assertEqual(self.wires[0][1], 1)
        self.assertEqual(reviews, [])
        self.assertIn('DeadlineAfterCall', result['stop_reason'])

    def test_review_time_uses_shared_deadline(self):
        def late_review(*args):
            self.clock.value = 901
            return True
        result = self.run_cases(review=late_review, deadline=900)
        self.assertEqual(self.adapter.calls, 1)
        self.assertIn('DeadlineAfterReview', result['stop_reason'])

    def test_stale_review_hash_or_incomplete_meaning_review_rejected(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, 'RUN', Path(folder)):
            row = {'records_sha256': 'current', 'output': self.outputs[0]}
            spec = {'id': '01-r1'}
            review = {'case_id': spec['id'], 'records_sha256': 'stale', 'decision': 'ACCEPT',
                'action_meaning_correct': True, 'rationale_claim_correct': True,
                'reason_correct': True, 'note': 'offline authored note'}
            path = Path(folder) / 'reviews/01-r1.json'
            write(path, review)
            with patch.object(runner.time, 'monotonic', return_value=0):
                self.assertFalse(runner.author_review(spec, row, 900))
                review['records_sha256'] = 'current'
                review['rationale_claim_correct'] = False
                write(path, review)
                self.assertFalse(runner.author_review(spec, row, 900))
                review['rationale_claim_correct'] = True
                write(path, review)
                self.assertTrue(runner.author_review(spec, row, 900))


if __name__ == '__main__':
    unittest.main()
