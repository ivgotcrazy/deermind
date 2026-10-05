"""Post-campaign contract repair; no change to frozen v1 and no provider calls."""
import json
from pathlib import Path
import unittest

from foundation.structured_output import matches_schema

ROOT=Path(__file__).resolve().parents[1]


class X5ProtocolContractTests(unittest.TestCase):
    def definition(self,version):
        return json.loads((ROOT/f'protocols/observation-x5-request-{version}.json').read_text(encoding='utf-8'))

    def test_repaired_criteria_are_expressible_in_output_schema(self):
        definition=self.definition('v2')
        schema=definition['output_contracts']['validation']['parameters']
        criterion_schema=schema['properties']['criteria']['items']
        self.assertEqual(set(criterion_schema['properties']['id']['enum']),{c['id'] for c in definition['criteria']})
        for criterion in definition['criteria']:
            self.assertTrue(matches_schema({'id':criterion['id'],'quotes':[],'rationale':'contract fixture','status':'PASS'},criterion_schema))

    def test_frozen_failure_remains_distinct_from_repair(self):
        old=self.definition('v1');new=self.definition('v2')
        criterion={'id':'request','quotes':[],'rationale':'contract fixture','status':'PASS'}
        old_schema=old['output_contracts']['validation']['parameters']['properties']['criteria']['items']
        new_schema=new['output_contracts']['validation']['parameters']['properties']['criteria']['items']
        self.assertFalse(matches_schema(criterion,old_schema))
        self.assertTrue(matches_schema(criterion,new_schema))
        self.assertEqual(old['criteria'],new['criteria'])
        self.assertEqual(old['validation_system'],new['validation_system'])
        # The closed v1 runner must continue naming its actual original protocol.
        fixture=json.loads((ROOT/'fixtures/composition-x5-v1.json').read_text(encoding='utf-8'))
        paths={Path(p).as_posix() for p in fixture['protocol_sha256']}
        self.assertIn('protocols/observation-x5-request-v1.json',paths)
        self.assertNotIn('protocols/observation-x5-request-v2.json',paths)


if __name__=='__main__':unittest.main()
