"""题内参考归类使用分开的父题证据与方法证据。"""

import unittest

from deermind.spaces.domain.analysis import accepted_output, location_tables
from deermind.spaces.domain.public import CLASSIFY, AnalysisOutput, Assessment, Finding
from pydantic import JsonValue


class DomainClassificationTests(unittest.TestCase):
    def test_reference_cannot_use_the_parent_definition_location(self) -> None:
        data: dict[str, JsonValue] = {
            "action": CLASSIFY,
            "candidate": {"body": {"content": {"blocks": [{}]}}},
            "parent": {"body": {"content": {"blocks": [{}]}}},
            "definitions": {"solution": {"approach": "合并比例"}, "task": {"name": "求部分量"}},
        }
        _, locations = location_tables(data)
        self.assertEqual(locations, {"task": {"D1": "/name"}, "solution": {"D2": "/approach"}})
        parent = Finding(
            criterion="题目要求",
            conclusion="符合",
            material_locations=["M2"],
            definition_locations=["D1"],
        )
        reference = Finding(
            criterion="解法过程",
            conclusion="符合",
            material_locations=["M1"],
            definition_locations=["D2"],
        )
        task = Assessment(candidate_key="task", result="matched", findings=[parent], issues=[])
        solution = Assessment(
            candidate_key="solution", result="matched", findings=[reference], issues=[]
        )
        self.assertIsNone(
            accepted_output(
                data, AnalysisOutput(draft=None, results=[task, solution], unresolved=[])
            )
        )
        wrong_reference = reference.model_copy(update={"definition_locations": ["D1"]})
        invalid = solution.model_copy(update={"findings": [wrong_reference]})
        with self.assertRaisesRegex(ValueError, "outside the supplied definition"):
            accepted_output(
                data, AnalysisOutput(draft=None, results=[task, invalid], unresolved=[])
            )
