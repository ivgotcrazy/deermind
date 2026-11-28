"""Publishing a book fixes local task identities and the criteria that assess them."""

import unittest
from datetime import UTC, datetime
from uuid import UUID, uuid4

from deermind.foundation.system.public.errors import RequestError
from deermind.product.materials.teaching_model import build_teaching
from deermind.product.public.material_editions import (
    ContentNode,
    ModelKnowledge,
    ModelMethod,
    ModelTask,
    TeachingDependency,
    TeachingModel,
)
from deermind.spaces.domain.public import TaskRef
from deermind.spaces.evaluation.assessment_models import definitions
from deermind.spaces.evaluation.conditions import resolve_conditions
from deermind.spaces.evaluation.public import (
    STANDARD_ASPECTS,
    AssessmentModel,
    EvidenceRule,
    MethodStandard,
    TaskStandard,
)


class BookModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chapter = ContentNode(
            node_id=uuid4(),
            parent_id=None,
            node_kind="section",
            sibling_order=1,
            content=None,
            covered_page_ids=[uuid4()],
        )
        self.task = ModelTask(
            key="recognize",
            task_type="knowledge",
            knowledge_key="fraction",
            insufficient_example="仅报答案",
            chapter_id=self.chapter.node_id,
            name="读懂分率",
            description="说明单位量",
            expected_output="说明分率",
            completion_conditions="写明部分与整体的关系",
            source_nodes=[self.chapter.node_id],
            methods=[
                ModelMethod(
                    key="diagram",
                    name="画图",
                    steps="标出单位量",
                    rationale="比较同一量",
                    applicability="已知整体",
                    dependencies=[],
                )
            ],
        )
        self.model = TeachingModel(
            knowledge=[
                ModelKnowledge(
                    key="fraction",
                    name="分率",
                    meaning="部分与整体之比",
                    applicability="单位量已知",
                )
            ],
            tasks=[self.task],
        )

    def test_new_edition_owns_new_definitions(self) -> None:
        first, second = uuid4(), uuid4()

        def ident(edition: UUID) -> TaskRef:
            entries, _, _ = build_teaching(edition, self.model, [self.chapter])
            return entries[0].task_ref

        self.assertEqual(ident(first), ident(first))
        self.assertNotEqual(ident(first), ident(second))

    def test_broken_graph_and_missing_source_rejected(self) -> None:
        dep = TeachingDependency(task_key=self.task.key, reason="准备")
        for changes in (
            {"source_nodes": [uuid4()]},
            {"knowledge_key": "unknown"},
            {"methods": [self.task.methods[0].model_copy(update={"dependencies": [dep]})]},
        ):
            model = self.model.model_copy(update={"tasks": [self.task.model_copy(update=changes)]})
            with self.subTest(changes=changes), self.assertRaises(RequestError):
                build_teaching(uuid4(), model, [self.chapter])

    def test_dependency_belongs_to_one_method_and_rename_preserves_identity(self) -> None:
        first = self.task.methods[0]
        uses = first.model_copy(
            update={"dependencies": [TeachingDependency(task_key=self.task.key, reason="识别分率")]}
        )
        other = first.model_copy(update={"key": "other", "name": "直接测量"})
        composite = self.task.model_copy(
            update={
                "key": "apply",
                "name": "计算",
                "task_type": "composite",
                "knowledge_key": None,
                "methods": [uses, other],
            }
        )
        model = self.model.model_copy(update={"tasks": [composite, self.task]})
        edition = uuid4()
        entries, _, _ = build_teaching(edition, model, [self.chapter])
        target = next(e for e in entries if e.name == "计算")
        self.assertEqual(target.prerequisites[0].method_refs, [target.method_refs[0]])
        self.assertEqual(target.method_knowledge[1], [])
        renamed = composite.model_copy(update={"name": "改名"})
        result, _, _ = build_teaching(
            edition, model.model_copy(update={"tasks": [self.task, renamed]}), [self.chapter]
        )
        self.assertEqual(result[-1].task_ref, target.task_ref)
        reverse = self.task.model_copy(
            update={
                "methods": [
                    first.model_copy(
                        update={
                            "dependencies": [TeachingDependency(task_key="apply", reason="无效")]
                        }
                    )
                ]
            }
        )
        with self.assertRaisesRegex(RequestError, "知识任务"):
            build_teaching(
                edition, model.model_copy(update={"tasks": [reverse, composite]}), [self.chapter]
            )
        for tasks in ([composite], [self.task, self.task.model_copy(update={"key": "second"})]):
            with self.assertRaises(RequestError):
                build_teaching(edition, model.model_copy(update={"tasks": tasks}), [self.chapter])

    def test_cross_chapter_dependency_and_indirect_cycle(self) -> None:
        second = self.chapter.model_copy(update={"node_id": uuid4()})
        first_method = self.task.methods[0]

        def method_to(key: str) -> ModelMethod:
            return first_method.model_copy(
                update={"dependencies": [TeachingDependency(task_key=key, reason="先辨认单位量")]}
            )

        later = self.task.model_copy(
            update={
                "key": "later",
                "task_type": "composite",
                "knowledge_key": None,
                "chapter_id": second.node_id,
                "source_nodes": [second.node_id],
                "methods": [method_to(self.task.key)],
            }
        )
        third = later.model_copy(update={"key": "third", "methods": [method_to("later")]})
        nodes = [self.chapter, second]
        edition = uuid4()
        graph = self.model.model_copy(update={"tasks": [third, later, self.task]})
        entries, _, _ = build_teaching(edition, graph, nodes)
        self.assertEqual(entries[1].prerequisites[0].task_ref, entries[0].task_ref)
        for dependency in ("third", "absent"):
            invalid = later.model_copy(update={"methods": [method_to(dependency)]})
            with self.subTest(dependency=dependency), self.assertRaises(RequestError):
                build_teaching(
                    edition, graph.model_copy(update={"tasks": [self.task, invalid, third]}), nodes
                )

    def test_distinct_assessment_sets_cannot_share_claim_identity(self) -> None:
        entries, _, _ = build_teaching(uuid4(), self.model, [self.chapter])
        entry = entries[0]
        method = MethodStandard(
            method_id=entry.method_refs[0].object_id,
            pass_description="说明单位量",
            fail_description="混淆单位量",
            unknown_description="缺少作答",
            aspects=[
                EvidenceRule(aspect=k, evidence="原文表现")
                for k in ("independent", "understanding", "transfer", "retention")
            ],
        )
        standard = TaskStandard(
            task_id=entry.task_ref.object_id,
            title=self.task.name,
            description="说明单位量",
            methods=[method],
        )
        model = AssessmentModel(
            model_id=uuid4(),
            extraction_id=uuid4(),
            name="课堂",
            number=1,
            revision=1,
            status="draft",
            created_at=datetime.now(UTC),
            claims=[standard],
        )
        expected = dict(zip([entry.task_ref], [entry.method_refs], strict=True))
        domain = uuid4()
        ref, definition = definitions(model, domain, expected)[0]
        for rule in definition.methods[0].aspect_rules:
            self.assertEqual(resolve_conditions(rule.condition_schema, rule.default_values, {}), {})
        self.assertEqual({a.code for a in definition.aspects}, set(STANDARD_ASPECTS))
        self.assertNotEqual(
            ref, definitions(model.model_copy(update={"model_id": uuid4()}), domain, expected)[0][0]
        )
        with self.assertRaises(RequestError):
            definitions(model.model_copy(update={"claims": []}), domain, expected)
