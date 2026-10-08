"""Exact representation and admission regression tests, not semantic evaluation."""
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from foundation.candidate_spans import QUOTE_SELECTIONS, expand_review, quote_spans, registry
from foundation.cases import EvidenceRecorder
from foundation.guarded_cases import setup_boundary
from foundation.llm import DeepSeekAdapter, LLMConfig
from foundation.protocol_preflight import check_observation_contract
from foundation.records import json_value
from foundation.runtime import ContractError
from foundation.single_task import SingleTaskWorld
import test_indexed_observation as indexed
from test_indexed_observation import review
from test_single_task_v2 import IndexedScriptedTransport, plan_v2

ROOT = Path(__file__).parents[1]
PROTOCOL = json.loads((ROOT / 'protocols/observation-feasibility-v1.json').read_text(encoding='utf-8'))


class FeasibilityInterfaceTests(unittest.TestCase):
    def test_disjoint_quotes_keep_exact_separate_text_and_legacy_rejects(self):
        payload = {'description': '第一句。中间内容。最后一句。'}
        raw = review(payload)
        raw['criteria'][0]['quotes'] = [{'span_ids': ['candidate_0', 'candidate_2']}]
        with self.assertRaises(ContractError):
            expand_review(raw, payload)
        out = expand_review(raw, payload, QUOTE_SELECTIONS)
        self.assertEqual(out['criteria'][0]['quotes'], [
            {'field': 'description', 'text': '第一句。'},
            {'field': 'description', 'text': '最后一句。'}])
        self.assertEqual(out['claims'][0]['text'], payload['description'])
        self.assertEqual(raw['criteria'][0]['quotes'][0]['span_ids'], ['candidate_0', 'candidate_2'])

    def test_bad_quote_handles_and_disjoint_claims_still_rejected(self):
        entries = registry({'a': 'first,second,third', 'b': 'fourth'})
        for ids in ([], ['missing'], ['candidate_0', 'candidate_0'],
                    ['candidate_1', 'candidate_0'], ['candidate_0', 'candidate_3']):
            with self.subTest(ids=ids), self.assertRaises(ContractError):
                quote_spans(ids, entries, QUOTE_SELECTIONS)
        payload = {'description': 'first,second,third'}
        raw = review(payload)
        raw['claims'][0]['span_ids'] = ['candidate_0', 'candidate_2']
        with self.assertRaises(ContractError):
            expand_review(raw, payload, QUOTE_SELECTIONS)

    def test_commit_reexpands_exact_quotes_and_rejects_tampered_wire(self):
        payload = {'description': '学习者报告120。仅作记录。尚无其他材料。'}
        for tamper in (False, True):
            with self.subTest(tamper=tamper):
                h, s, r, t, ctx, _, _ = setup_boundary(prepare_candidate=False,
                    protocol_payload=PROTOCOL, destination='https://api.deepseek.com/beta')
                c = r.propose(ctx, 'O', 'r1', payload)
                raw = review(payload)
                raw['criteria'][0]['quotes'] = [{'span_ids': ['candidate_0', 'candidate_2']}]
                adapter = indexed.IndexedObservationTests().adapter(payload, raw=raw)
                result = r.validate_with_llm(t, c, adapter)
                self.assertEqual(result.status, 'PASS')
                if tamper:
                    record = h.get(result.execution).payload
                    record['wire_output']['criteria'][0]['quotes'][0]['span_ids'] = ['missing']
                    forged = r.execution('SemanticValidationExecution', ctx.subject, record)
                    r._reviews[result.identity] = replace(result, execution=forged)
                outcome = r.commit(t, c, result.identity)
                self.assertEqual(outcome.status == 'Committed', not tamper)
                self.assertEqual(h.get(c.record.ref) is not None, not tamper)

    def test_unknown_quote_encoding_fails_preflight(self):
        self.assertEqual(check_observation_contract(PROTOCOL)['status'], 'PASS')
        wrong = deepcopy(PROTOCOL)
        wrong['criterion_quote_encoding'] = 'guess'
        with self.assertRaisesRegex(ValueError, 'UnsupportedCriterionQuoteEncoding'):
            check_observation_contract(wrong)

    def test_execution_reference_is_usable_but_forged_reference_cannot_commit(self):
        for forged in (False, True):
            with self.subTest(forged=forged), tempfile.TemporaryDirectory() as tmp, \
                    closing(EvidenceRecorder(Path(tmp) / 'case.jsonl')) as e:
                plan = plan_v2()
                plan['protocols'] = {'work': 'src/spike/protocols/observation-feasibility-v1.json',
                                    'policy': 'src/spike/protocols/policy-feasibility-v1.json'}
                world = SingleTaskWorld(e, 'interface', plan)
                transport = IndexedScriptedTransport()
                transport.outcome = 'NoIntervention'
                def inject():
                    ref = json_value(world.help)
                    if forged:
                        ref['identity'] = 'not-in-this-context'
                    transport.policy_changes['context_refs'] = [ref]
                transport.callback = inject
                adapter = DeepSeekAdapter(LLMConfig('OFFLINE', base_url=plan['model']['base_url'],
                    max_calls=10, max_output_tokens=4096), transport)
                world.receive(plan['sessions'][2]['inputs'][0])
                result = world.process(adapter)
                self.assertEqual(result['policy_commit']['status'] == 'Committed', not forged)
                if forged:
                    self.assertEqual(result['policy_commit']['reason'], 'PolicyContextReferenceInvalid')
                self.assertEqual(result['displayed'], [])
                e.close()


if __name__ == '__main__':
    unittest.main()
