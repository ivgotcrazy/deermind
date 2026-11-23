"""目标状态尊重观测精度、方法边界和证据条件。"""

import unittest
from decimal import Decimal
from uuid import uuid4

from deermind.abstractions.events import Ref
from deermind.product.public.learning_targets import (
    GoalItem,
    MethodRequirement,
    TargetAspect,
    TargetAspectRef,
    TaskConditions,
)
from deermind.spaces.domain.public import SolutionRef
from deermind.spaces.evaluation.goal_calculation import CoveredAnswer, Observation, derive_target
from deermind.spaces.evaluation.public import ClaimRef


class GoalCalculationTests(unittest.TestCase):
    def test_threshold_needs_eligible_evidence_and_precise_observation(self) -> None:
        claim = ClaimRef(claim_id=uuid4(), revision=1)
        first, second = (
            SolutionRef(kind="solution", object_id=uuid4(), version=1) for _ in range(2)
        )
        chapter = uuid4()
        aspect = TargetAspect(
            aspect_ref=TargetAspectRef(claim_ref=claim, aspect_code="independent"),
            condition_values={"help": "none"},
        )
        item = GoalItem(
            item_id=uuid4(),
            title="四分之一",
            claim_ref=claim,
            chapter_refs=[chapter],
            task_conditions=TaskConditions(description="增加四分之一"),
            method_mode="each",
            methods=[
                MethodRequirement(method_ref=method, chapter_refs=[chapter], aspects=[aspect])
                for method in (first, second)
            ],
        )
        self.assertEqual(derive_target([item], {}, {}).attainment, "unknown")
        evidence = Ref(owner="evaluation", type="evidence", id=str(uuid4()))
        correct_scope = CoveredAnswer(evidence, "eligible", {"help": "none"}, "增加四分之一")
        other_scope = CoveredAnswer(evidence, "eligible", {"help": "none"}, "增加五分之一")
        first_key, second_key = (claim, first, "independent"), (claim, second, "independent")
        snapshot = {
            first_key: Observation(Decimal("0.9000"), [correct_scope]),
            second_key: Observation(Decimal("0.96"), [other_scope]),
        }
        self.assertEqual(derive_target([item], {}, snapshot).attainment, "unknown")
        alternative = item.model_copy(update={"method_mode": "any_one"})
        self.assertEqual(derive_target([alternative], {}, snapshot).attainment, "met")
        snapshot[second_key] = Observation(Decimal("0.89999"), [correct_scope])
        self.assertEqual(derive_target([item], {}, snapshot).attainment, "needs_strengthening")
        gaps = {(item.item_id, second, "independent"): ["missing_aspect_rule"]}
        self.assertEqual(derive_target([item], gaps, snapshot).readiness, "unprepared")
        self.assertEqual(derive_target([alternative], gaps, snapshot).attainment, "met")
