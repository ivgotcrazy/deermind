"""学习目标保留章节来源，拒绝错章和管理员自选概率。"""

import unittest
from uuid import uuid4

from deermind.abstractions.events import Ref
from deermind.foundation.system.public.errors import RequestError
from deermind.product.learning.requirements import prepare_item
from deermind.product.public.chapter_associations import ChapterAssociationView
from deermind.product.public.learning_targets import (
    GoalItemDraft,
    MethodRequirement,
    TargetAspect,
    TargetAspectRef,
    TaskConditions,
)
from deermind.spaces.domain.public import SolutionRef, TaskRef
from deermind.spaces.evaluation.conditions import resolve_conditions, verify_schema
from deermind.spaces.evaluation.public import (
    AspectDefinition,
    AspectRule,
    ClaimDefinition,
    ClaimRef,
    ClaimView,
    MethodDefinition,
)
from pydantic import JsonValue


class LearningTargetScopeTests(unittest.TestCase):
    def test_methods_use_the_union_and_keep_specific_chapters(self) -> None:
        task = TaskRef(kind="task", object_id=uuid4(), version=1)
        first, second = [
            SolutionRef(kind="solution", object_id=uuid4(), version=1) for _ in range(2)
        ]
        chapters = [uuid4(), uuid4()]
        claim_ref = ClaimRef(claim_id=uuid4(), revision=1)
        claim = ClaimView(
            claim_ref=claim_ref,
            gaps=[],
            definition=ClaimDefinition(
                domain_id=uuid4(),
                task_ref=task,
                title="分数",
                description="求新量",
                aspects=[
                    AspectDefinition(code="independent", label="独立", description="独立作答")
                ],
                criteria=[],
                methods=[
                    MethodDefinition(method_ref=method, criterion_ids=[], aspect_rules=[])
                    for method in (first, second)
                ],
            ),
        )
        links = {
            chapter: ChapterAssociationView(
                association_ref=Ref(
                    owner="product", type="chapter_association", id=str(uuid4()), revision=1
                ),
                task_ref=task,
                method_refs=[method],
                active=True,
            )
            for chapter, method in zip(chapters, (first, second), strict=True)
        }
        aspect = TargetAspect(
            aspect_ref=TargetAspectRef(claim_ref=claim_ref, aspect_code="independent"),
            condition_values={},
        )
        item = GoalItemDraft(
            title="四分之一",
            claim_ref=claim_ref,
            chapter_refs=chapters,
            task_conditions=TaskConditions(description="增加四分之一", parameter_values={}),
            method_mode="each",
            methods=[
                MethodRequirement(method_ref=method, chapter_refs=[chapter], aspects=[aspect])
                for chapter, method in zip(chapters, (first, second), strict=True)
            ],
        )

        def conditions(rule: AspectRule, values: dict[str, JsonValue]) -> dict[str, JsonValue]:
            return resolve_conditions(rule.condition_schema, rule.default_values, values)

        result, gaps, sources = prepare_item(item, claim, links, set(), "/items/0", conditions)
        self.assertEqual(result.methods, item.methods)
        self.assertEqual(len(sources), 2)
        self.assertEqual({gap.code for gap in gaps}, {"missing_criteria", "missing_aspect_rule"})
        wrong = item.methods[0].model_copy(update={"chapter_refs": chapters})
        misapplied = item.model_copy(update={"methods": [wrong, item.methods[1]]})
        with self.assertRaises(RequestError) as caught:
            prepare_item(misapplied, claim, links, set(), "/items/0", conditions)
        self.assertEqual(caught.exception.code, "invalid_reference")

    def test_condition_schema_rejects_probability_override(self) -> None:
        with self.assertRaisesRegex(ValueError, "禁止配置"):
            verify_schema({"type": "object", "properties": {"threshold": {"type": "number"}}}, {})
