import json
from pathlib import Path
import tempfile
import unittest

from foundation.cases import EvidenceRecorder
from foundation.llm import LLMConfig
from foundation.runtime import ContractError
from foundation.security import AuthorityGrant
from foundation.security_cases import SecurityWorld, envelope, extra_controls, request
from run_security_validation import load_design, run_branch, summarize


class SecurityCampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.e = EvidenceRecorder(Path(self.tmp.name)/'evidence.jsonl')
        self.addCleanup(self.e.close)
        self.fixture, self.definition = load_design()
        self.base = SecurityWorld(self.e, self.definition)
        self.config = LLMConfig('TEST-ONLY', self.definition['provider_endpoint'], max_calls=1)

    @staticmethod
    def transport(value):
        def response(url, key, wire, timeout):
            return {'choices': [{'finish_reason': 'tool_calls', 'message': {'content': None,
                'tool_calls': [{'type': 'function', 'function': {'name': 'submit_tool_request', 'arguments': json.dumps(value)}}]}}]}
        return response

    def test_all_ten_attacks_traverse_real_adapter_and_shared_backend(self):
        original = self.base.protected_state()
        for variant in self.fixture['variants']:
            row = run_branch(self.base, self.e, variant, 1, self.config, self.transport(envelope(variant['attack'])))
            self.assertEqual(row['result'], 'PASS', row)
            self.assertEqual(row['model_result'], 'DENIED')
            self.assertEqual(row['injected_result'], 'DENIED')
            self.assertEqual(row['model_calls'], 1)
        self.assertEqual(self.base.protected_state(), original)

    def test_refusal_does_not_hide_backend_injection_coverage(self):
        v = self.fixture['variants'][0]
        row = run_branch(self.base, self.e, v, 1, self.config, self.transport(envelope(v['attack'], 'REFUSE')))
        self.assertEqual((row['model_result'], row['injected_result'], row['coverage']), ('MODEL_REFUSED', 'DENIED', 'COMPLETE'))

    def test_allowed_alternative_is_distinct_from_refusal_or_attack(self):
        v = self.fixture['variants'][0]
        raw = envelope(request())
        raw['claimed_principal'] = 'f-workload'
        row = run_branch(self.base, self.e, v, 1, self.config, self.transport(raw))
        self.assertEqual((row['result'], row['model_result']), ('PASS', 'ALLOWED'))

    def test_provider_failure_preserves_injected_evidence_but_is_incomplete(self):
        def broken(*args): raise TimeoutError()
        row = run_branch(self.base, self.e, self.fixture['variants'][0], 1, self.config, broken)
        self.assertEqual((row['reason'], row['injected_result'], row['coverage']), ('ProviderTimeout', 'DENIED', 'INCOMPLETE'))
        self.assertEqual(summarize([row], self.fixture, None)['status'], 'NON_SUCCESS')

    def test_fixed_extra_controls_and_full_audit(self):
        extra_controls(self.base, self.e, self.fixture['variants'][0])
        self.assertTrue(all(c['passed'] for c in self.e.checks), [c for c in self.e.checks if not c['passed']])

    def test_model_invented_authority_never_installs_grants(self):
        w = self.base.branch(self.e)
        w.prepare(self.fixture['variants'][0])
        original = w.security.describe_grants()
        c = w.injected(request('GovernanceActivateVersion', resource='ObservationSemantics'))
        self.assertEqual(w.gateway.dispatch(w.token, c)['status'], 'DENIED')
        self.assertEqual(w.security.describe_grants(), original)
        self.assertEqual(w.effects, [])

    def test_invalid_parameter_json_has_no_dispatch_effect(self):
        w = self.base.branch(self.e)
        w.prepare(self.fixture['variants'][0])
        raw = request('candidate', parameters=[{'name':'action', 'value':'{"a":1,"a":2}'}])
        c = w.injected(raw)
        with self.assertRaisesRegex(ContractError, 'MalformedToolParameters'):
            w.gateway.dispatch(w.token, c)
        self.assertFalse(any(r.kind == 'DelegatedCandidateBuffered' for r in w.h.executions.records()))

    def test_privileged_mock_handler_is_reachable_only_after_trusted_grant(self):
        w = self.base.branch(self.e)
        w.prepare(self.fixture['variants'][0])
        c = w.injected(request('GovernanceActivateVersion', resource='ObservationSemantics'))
        self.assertEqual(w.gateway.dispatch(w.token, c)['status'], 'DENIED')
        self.assertEqual(w.effects, [])
        w.security.install_authority(AuthorityGrant('TEST-ADMIN-GRANT', w.principal, 'learning', 'learner-A',
            ('ObservationSemantics',), ('GovernanceActivateVersion',), 10000))
        self.assertEqual(w.gateway.dispatch(w.token, c)['status'], 'ALLOWED')
        self.assertEqual(len(w.effects), 1)


if __name__ == '__main__': unittest.main()
