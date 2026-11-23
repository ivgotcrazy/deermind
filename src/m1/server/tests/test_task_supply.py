"""已存题目按固定 Task、方法、用途和学生接触事实筛选。"""

from unittest import TestCase
from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.abstractions.task_supply import TaskSupplyRequested
from deermind.spaces.domain.generated_tasks import (
    GeneratedQuestion,
    QualityChecks,
    QuestionCheck,
    accepted_numbers,
    materialize,
)
from deermind.spaces.domain.public import InstanceView
from deermind.spaces.domain.supply_selection import select_instances
from pydantic import JsonValue

TASK = UUID(int=1)
METHOD = UUID(int=2)
SCOPE = UUID(int=3)


def ref(kind: str, identity: UUID) -> Ref:
    return Ref(owner="domain", type=kind, id=str(identity), version=1)


def instance(value: int, solution: UUID = METHOD, *, answer: bool = True) -> InstanceView:
    number = UUID(int=value)
    statement: dict[str, JsonValue] = {
        "schema_version": "1",
        "role": "statement",
        "source_refs": [],
        "data_tables": [],
        "blocks": [
            {
                "block_id": "text",
                "type": "paragraph",
                "provenance": {"source_refs": [], "transformation": "generated"},
                "payload": {"spans": [{"type": "text", "text": f"{value} 增加四分之一是多少？"}]},
            }
        ],
    }
    return InstanceView.model_validate(
        {
            "instance_ref": {"object_id": number, "version": 1},
            "is_deleted": False,
            "content": {
                "title": f"求 {value} 的新量",
                "task_ref": {"kind": "task", "object_id": TASK, "version": 1},
                "statement": statement,
                "answer_basis": {**statement, "role": "reference"} if answer else None,
                "reference_solutions": [
                    {
                        "reference_id": number,
                        "solution_ref": {"kind": "solution", "object_id": solution, "version": 1},
                        "content": {**statement, "role": "reference"},
                        "origin": "admin_authored",
                        "source_refs": [],
                    }
                ],
                "source_refs": [],
            },
        }
    )


def request() -> TaskSupplyRequested:
    basis = Ref(owner="interaction", type="input", id=str(SCOPE))
    return TaskSupplyRequested(
        request_ref=basis,
        supply_input_ref=basis,
        domain_id=SCOPE,
        activity_ref=Ref(owner="interaction", type="activity", id=str(SCOPE)),
        purpose="assessment",
        task_ref=ref("task", TASK),
        allowed_method_refs=[ref("solution", METHOD)],
        assessment_constraints_ref=basis,
        assessment_constraints=None,
        method_source_refs=[Ref(owner="product", type="chapter_association", id=str(SCOPE))],
        exposure_refs=[],
        exposed_instances=[],
        count=1,
        records=[],
    )


class TaskSupplyTests(TestCase):
    def test_generated_question_requires_complete_independent_check(self) -> None:
        checks = QualityChecks(
            checks=[
                QuestionCheck(question_number=1, judgment="pass", reason="列式成立"),
                QuestionCheck(question_number=2, judgment="unknown", reason="条件不足"),
            ]
        )
        self.assertEqual(accepted_numbers(checks, 2), [1])
        self.assertEqual(accepted_numbers(checks, 3), [])
        self.assertEqual(
            accepted_numbers(QualityChecks(checks=[*checks.checks, checks.checks[0]]), 2), []
        )

    def test_generation_cannot_choose_method_outside_fixed_request(self) -> None:
        original = instance(20).content
        reference = original.reference_solutions[0]
        assert original.answer_basis is not None
        candidate = GeneratedQuestion(
            title=original.title,
            statement="20 增加四分之一是多少？",
            answer_basis="25",
            method_number=1,
            method_body="20 × (1 + 1/4) = 25",
        )
        question = materialize(candidate, original.task_ref, [reference.solution_ref], SCOPE, 1)
        self.assertEqual(question.reference_solutions[0].origin, "system_generated")
        self.assertEqual(question.reference_solutions[0].solution_ref, reference.solution_ref)
        self.assertEqual(
            question.reference_solutions[0].reference_id,
            materialize(candidate, original.task_ref, [reference.solution_ref], SCOPE, 1)
            .reference_solutions[0]
            .reference_id,
        )
        with self.assertRaisesRegex(ValueError, "outside the request"):
            materialize(candidate, original.task_ref, [], SCOPE, 1)

    def test_existing_question_must_match_method_and_purpose_and_be_unseen(self) -> None:
        stock = [instance(20), instance(24, UUID(int=9)), instance(28, answer=False), instance(32)]
        requested = request().model_copy(
            update={"exposed_instances": [ref("task_instance", UUID(int=20))]}
        )
        selected, unfilled = select_instances(requested, stock)
        self.assertIsNone(unfilled)
        self.assertEqual(
            [item.instance.instance_ref.object_id for item in selected], [UUID(int=32)]
        )

    def test_unknown_history_or_unverified_scope_does_not_supply_a_question(self) -> None:
        for fields, reason in (
            ({"exposed_instances": None}, "exposure_unknown"),
            ({"assessment_constraints": "要求新情境的迁移题"}, "requires_semantic_check"),
        ):
            selected, unfilled = select_instances(
                request().model_copy(update=fields), [instance(20)]
            )
            self.assertEqual(selected, [])
            assert unfilled is not None
            self.assertEqual(unfilled.reason, reason)
