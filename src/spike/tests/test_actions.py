import tempfile
import unittest
from pathlib import Path

from foundation.action_cases import ActionWorld, d1, d2
from foundation.actions import ActionRuntime
from foundation.cases import EvidenceRecorder, correct
from foundation.runtime import ContractError
from foundation.security import AccessDenied


class ActionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.e = EvidenceRecorder(Path(directory.name) / 'evidence.jsonl')
        self.addCleanup(self.e.close)
        self.w = ActionWorld(self.e)
        self.w.prepare_action()

    def assert_no_effect(self, result):
        self.assertEqual(result['status'], 'NotOccurred')
        self.assertIsNone(result['occurrence_ref'])
        self.assertFalse(any(r.kind in ('ActionOccurrence', 'DisplayAcknowledgement')
            for space in (self.w.h.facts, self.w.h.executions) for r in space.records()))

    def test_effect_rechecks_authority_and_emits_security_signal(self):
        self.w.security.revoke('D-effect-authority', self.w.intent)
        self.assert_no_effect(self.w.execute('OCCUR_FULL'))
        self.assertTrue(any(r.kind == 'SecuritySignal' for r in self.w.h.audit.records()))

    def test_effect_rechecks_data_authority(self):
        self.w.security.revoke('D-effect-data', self.w.intent)
        result = self.w.execute('OCCUR_FULL')
        self.assert_no_effect(result)
        self.assertIn('DataAuthorityDenied', result['reason'])

    def test_expiry_is_checked_before_acknowledgement(self):
        self.w.h.clock.advance(1000)
        result = self.w.execute('OCCUR_FULL')
        self.assert_no_effect(result)
        self.assertEqual(result['reason'], 'IntentExpired')

    def test_correction_of_policy_basis_prevents_effect(self):
        correct(self.w.h, self.w.before_observation)
        result = self.w.execute('OCCUR_FULL')
        self.assert_no_effect(result)
        self.assertIn('Corrected', result['reason'])

    def test_exact_payload_cannot_be_swapped_at_effect_and_partial_is_actual(self):
        with self.assertRaises(TypeError):
            self.w.actions.execute(self.w.tokens['interaction'], self.w.intent, exact_payload='Answer is 105')
        with self.assertRaises(ContractError):
            self.w.execute('OCCUR_PARTIAL', 10000)
        self.w.execute('OCCUR_PARTIAL', 4)
        view = self.w.exposure(self.w.response('after'))
        self.assertEqual(view['exposures'][0]['payload'], '再检查一')
        self.assertEqual(view['exposures'][0]['completeness'], 'PARTIAL')

    def test_idempotency_survives_new_executor_instance_and_unknown_is_not_retried(self):
        result = self.w.execute('INDETERMINATE')
        self.w.allow_reads()
        again = ActionRuntime(self.w.runtime).execute(self.w.tokens['interaction'], self.w.intent)
        self.assertEqual(again, self.w.result_ref)
        self.assertEqual(result['status'], 'Indeterminate')
        self.assertFalse(any(r.kind == 'ActionOccurrence' for r in self.w.h.facts.records()))
        with self.assertRaises(ContractError):
            self.w.actions.create_intent(self.w.tokens['interaction'], self.w.policy,
                expires_at=self.w.h.clock.now + 5, idempotency_key='D-hint-once')

    def test_lineage_requires_current_read_authority(self):
        self.w.execute('OCCUR_FULL')
        response = self.w.response('after')
        self.w.exposure(response)
        self.w.security.revoke(self.w.tokens['evaluation'], self.w.intent)
        with self.assertRaises(AccessDenied):
            self.w.actions.exposure_for(self.w.tokens['evaluation'], response)

    def test_committed_different_payload_does_not_expand_effect_grant(self):
        payload = {**self.w.h.get(self.w.policy).payload, 'exact_payload': 'The answer is 105.'}
        altered = self.w.commit_scripted('PolicyOutcome', 'D-policy-altered', payload,
            (self.w.before_observation, self.w.action))
        self.w.allow_reads()
        with self.assertRaises(AccessDenied):
            self.w.actions.create_intent(self.w.tokens['interaction'], altered,
                expires_at=self.w.h.clock.now + 100, idempotency_key='another-key')
        self.assertEqual(sum(r.kind == 'ActionIntent' for r in self.w.h.executions.records()), 1)

    def test_history_survives_later_correction_and_time_is_not_rewritten(self):
        response = self.w.response('early')
        self.w.execute('OCCUR_FULL')
        before = self.w.exposure(response)
        correct(self.w.h, self.w.before_observation)
        after = self.w.exposure(response)
        self.assertEqual(before, after)
        self.assertFalse(after['exposures'][0]['before_response'])

    def test_declared_scenarios_all_checks_pass(self):
        d1(self.e)
        d2(self.e)
        self.assertTrue(self.e.checks)
        self.assertEqual([c for c in self.e.checks if not c['passed']], [])


if __name__ == '__main__':
    unittest.main()
