"""题目候选与检查结论使用固定内容合同，身份由 Domain 分配。"""

from typing import Annotated, Literal
from uuid import UUID, uuid5

from pydantic import Field, StringConstraints

from deermind.abstractions.events import FactModel
from deermind.spaces.domain.public import ReferenceSolution, SolutionRef, TaskInstance, TaskRef
from deermind.spaces.domain.rich_content import RichContent

type Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
type QuestionText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)
]


class GeneratedQuestion(FactModel):
    title: Title
    statement: QuestionText
    answer_basis: QuestionText
    method_number: Annotated[int, Field(gt=0)]
    method_body: QuestionText


class GeneratedQuestions(FactModel):
    questions: list[GeneratedQuestion]


class QuestionCheck(FactModel):
    question_number: Annotated[int, Field(gt=0)]
    judgment: Literal["pass", "fail", "unknown"]
    reason: Title


class QualityChecks(FactModel):
    checks: list[QuestionCheck]


def paragraph(text: str, role: Literal["statement", "reference"]) -> RichContent:
    return RichContent.model_validate(
        {
            "schema_version": "1",
            "role": role,
            "source_refs": [],
            "data_tables": [],
            "blocks": [
                {
                    "block_id": "p",
                    "type": "paragraph",
                    "provenance": {"source_refs": [], "transformation": "generated"},
                    "payload": {"spans": [{"type": "text", "text": text}]},
                }
            ],
        }
    )


def materialize(
    candidate: GeneratedQuestion,
    task: TaskRef,
    methods: list[SolutionRef],
    request: UUID,
    question_number: int,
) -> TaskInstance:
    """校验候选的结构、来源及方法，暂不保存。"""
    if candidate.method_number > len(methods):
        # 候选引用的方法序号超出本次请求提供的方法范围。
        raise ValueError("Generated question referred to a method outside the request")
    return TaskInstance(
        title=candidate.title,
        task_ref=task,
        statement=paragraph(candidate.statement, "statement"),
        answer_basis=paragraph(candidate.answer_basis, "reference"),
        reference_solutions=[
            ReferenceSolution(
                reference_id=uuid5(request, f"question:{question_number}:reference"),
                solution_ref=methods[candidate.method_number - 1],
                content=paragraph(candidate.method_body, "reference"),
                origin="system_generated",
                source_refs=[],
            )
        ],
        source_refs=[],
    )


def accepted_numbers(checks: QualityChecks, count: int) -> list[int]:
    """每道候选必须有一条确定检查。缺失和未知都不能把题投入使用。"""
    by_number = {item.question_number: item for item in checks.checks}
    if len(checks.checks) != len(by_number) or by_number.keys() != set(range(1, count + 1)):
        # 检查编号重复或未覆盖全部候选，整体不接受。
        return []
    return [number for number, item in sorted(by_number.items()) if item.judgment == "pass"]
