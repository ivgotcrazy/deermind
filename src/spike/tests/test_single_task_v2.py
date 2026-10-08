"""The same M1-M7 mechanical checks with the v2 interface and scripted labels."""
import json
from pathlib import Path

from foundation.candidate_spans import registry
from foundation.single_task import SingleTaskWorld, load_plan
import test_single_task as original_tests

ROOT = Path(__file__).parents[3]


def plan_v2():
    value = json.loads((ROOT / 'src/spike/fixtures/single-task-prototype-v2.json').read_text(encoding='utf-8'))
    original = load_plan()
    for key in ('sessions', 'actions', 'task', 'budget'):
        if value[key] != original[key]:
            raise ValueError('ChangedAcceptanceFixture:' + key)
    return value


class IndexedScriptedTransport(original_tests.ScriptedTransport):
    """Offline fixtures only. Never used by the real runner to repair responses."""
    def __call__(self, url, key, wire, timeout):
        response = super().__call__(url, key, wire, timeout)
        function = response['choices'][0]['message']['tool_calls'][0]['function']
        name = function['name']
        body = json.loads(wire['messages'][1]['content'])
        if not isinstance(body, dict) or 'candidate_registry' not in body:
            return response
        value = json.loads(function['arguments'])
        ids = [r['handle'] for r in body['candidate_registry']]
        if name in ('submit_responsibility', 'submit_extraction'):
            for segment in value['segments']:
                segment.pop('field')
                segment.pop('text')
                segment['span_ids'] = ids
        elif name == 'submit_review':
            for criterion in value['criteria']:
                criterion['quotes'] = [{'span_ids': ids}]
            for claim in value['claims']:
                claim.pop('field')
                claim.pop('text')
                claim['span_ids'] = ids
        function['arguments'] = json.dumps(value, ensure_ascii=False)
        return response


class SingleTaskV2Tests(original_tests.SingleTaskTests):
    def setUp(self):
        super().setUp()
        self.plan = plan_v2()
        self.transport = IndexedScriptedTransport()
        self.adapter.transport = self.transport
        self.w = SingleTaskWorld(self.e, 'test', self.plan)
