"""从本次采用中固定例题或练习的 Task 与方法范围。"""

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import timedelta
from typing import Literal
from uuid import UUID, uuid5

from deermind.abstractions.events import FactModel, Ref
from deermind.abstractions.executions import Execution, RunInput
from deermind.abstractions.task_supply import COMPLETED, REQUESTED, TaskSupplyRequested
from deermind.abstractions.waits import Condition, Wait
from deermind.foundation.system.waits.service import Waits
from deermind.product.public.courses import CourseSnapshot
from deermind.spaces.domain.public import TaskRef
from deermind.spaces.interaction.conversation import Conversation, draft, ref
from deermind.spaces.interaction.public import ActivityView, QuestionPart
from deermind.spaces.interaction.supply_wait import PROBE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class TeachingQuestion(FactModel):
    purpose: Literal["example", "practice"]
    task: TaskRef


class TeachingCard(FactModel):
    part: QuestionPart
    instance_ref: Ref
    method_refs: list[Ref]
    supply_event_id: UUID


def teaching_options(course: CourseSnapshot) -> list[TaskRef]:
    """同一固定 Task 跨章采用时仍只给出一个供题选项。"""
    options: dict[tuple[UUID, int], TaskRef] = {}
    for chapter in course.chapters:
        for link in chapter.associations:
            if link.active and link.method_refs:
                options[(link.task_ref.object_id, link.task_ref.version)] = link.task_ref
    return list(options.values())


def teaching_sources(course: CourseSnapshot, task: TaskRef) -> tuple[list[Ref], list[Ref]]:
    """汇总课程实际采用的方法，同时保留每个相关章节的关联来源。"""
    methods: dict[tuple[UUID, int], Ref] = {}
    sources: list[Ref] = []
    for chapter in course.chapters:
        for link in chapter.associations:
            if not link.active or link.task_ref != task or not link.method_refs:
                continue
            sources.append(link.association_ref)
            for method in link.method_refs:
                methods[(method.object_id, method.version)] = Ref(
                    owner="domain",
                    type="solution",
                    id=str(method.object_id),
                    version=method.version,
                )
    return list(methods.values()), sources


def question_trigger(identity: UUID) -> UUID:
    return uuid5(identity, "teaching-supply")


async def wait_for_question(
    db: AsyncConnection,
    conversation: Conversation,
    waits: Waits,
    run: RunInput,
    work: Execution,
    leaf: ActivityView,
    course: CourseSnapshot,
    question: TeachingQuestion,
    domain_for: Callable[[AsyncConnection, UUID], Awaitable[UUID]],
    principal: UUID,
    request_id: str,
) -> Wait | None:
    methods, sources = teaching_sources(course, question.task)
    if not methods:
        return None
    now = await db.scalar(text("SELECT clock_timestamp()"))
    deadline = min(now + timedelta(seconds=180), run.deadline_at - timedelta(seconds=20))
    if deadline <= now:
        return None
    scope = work.scope_id
    identity = question_trigger(work.execution_id)
    owner = ref("supply_request", identity)
    recorded = await db.scalar(
        text("SELECT 1 FROM runtime.events WHERE event_id=:id"), {"id": identity}
    )
    if recorded is None:
        history = (
            await db.execute(
                text(
                    "SELECT instance_ref,source_event_id FROM interaction.task_uses "
                    "WHERE scope_id=:scope AND instance_ref IS NOT NULL ORDER BY prepared_at"
                ),
                {"scope": scope},
            )
        ).all()
        requested = TaskSupplyRequested(
            request_ref=owner,
            supply_input_ref=work.input_ref,
            domain_id=await domain_for(db, scope),
            activity_ref=ref("activity", leaf.activity_ref.activity_id, leaf.activity_ref.revision),
            purpose=question.purpose,
            task_ref=Ref(
                owner="domain",
                type="task",
                id=str(question.task.object_id),
                version=question.task.version,
            ),
            allowed_method_refs=methods,
            assessment_constraints_ref=owner,
            assessment_constraints=None,
            method_source_refs=sources,
            exposure_refs=[
                Ref(owner="interaction", type="task_use_event", id=str(item.source_event_id))
                for item in history
            ],
            exposed_instances=list(
                dict.fromkeys(Ref.model_validate(item.instance_ref) for item in history)
            ),
            count=1,
            records=[],
        )
        trigger = replace(draft(scope, REQUESTED, owner, requested, request_id), event_id=identity)
        await conversation.append(db, scope, principal, UUID(work.acceptance_key), [trigger])
    return await waits.register(
        db,
        run,
        step_key="teaching_supply",
        owner=owner,
        condition=Condition(
            event_types=[COMPLETED],
            scope_kind="learning_space",
            scope_id=scope,
            equals={"producer": "domain", "correlation_id": str(identity)},
        ),
        probe_ref=PROBE,
        deadline=deadline,
        reserve_seconds=20,
    )
