"""从本次采用中固定例题或练习的 Task 与方法范围。"""

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid5

from deermind.abstractions.events import EventDraft, FactModel, Ref
from deermind.abstractions.executions import Execution, RunInput
from deermind.abstractions.task_supply import COMPLETED, REQUESTED, TaskSupplyRequested
from deermind.abstractions.waits import Condition, Wait, WaitCall
from deermind.foundation.system.executions import store
from deermind.foundation.system.executions.contracts import Registry
from deermind.foundation.system.waits.service import Waits
from deermind.product.public.courses import CourseSnapshot
from deermind.spaces.domain.public import TaskRef
from deermind.spaces.interaction import conversation_facts as facts
from deermind.spaces.interaction import history, task_facts
from deermind.spaces.interaction.conversation import Conversation, draft, ref
from deermind.spaces.interaction.public import ActivityView, QuestionPart
from deermind.spaces.interaction.supply_wait import PROBE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

if TYPE_CHECKING:
    from deermind.spaces.interaction.student_context import ActivityConfig


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
            # 只收集启用且带方法的关联，按任务编号+版本去重。
            if link.active and link.method_refs:
                options[(link.task_ref.object_id, link.task_ref.version)] = link.task_ref
    return list(options.values())


def teaching_sources(course: CourseSnapshot, task: TaskRef) -> tuple[list[Ref], list[Ref]]:
    """汇总课程实际采用的方法，同时保留每个相关章节的关联来源。"""
    methods: dict[tuple[UUID, int], Ref] = {}
    sources: list[Ref] = []
    for chapter in course.chapters:
        for link in chapter.associations:
            # 跳过未启用、任务不符或无方法的关联。
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
        # 该任务在课程中没有可用方法，不发起供题。
        return None
    now = await db.scalar(text("SELECT clock_timestamp()"))
    deadline = min(now + timedelta(seconds=180), run.deadline_at - timedelta(seconds=20))
    if deadline <= now:
        # 剩余时间已不足以预留等待，不发起。
        return None
    scope = work.scope_id
    identity = question_trigger(work.execution_id)
    owner = ref("supply_request", identity)
    recorded = await db.scalar(
        text("SELECT 1 FROM runtime.events WHERE event_id=:id"), {"id": identity}
    )
    if recorded is None:
        # 供题请求事件尚未落库，先追加事件再登记等待。
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


def presented_card(
    scope: UUID,
    card: TeachingCard,
    leaf: ActivityView,
    saved_activity: history.ActivityState,
    message: facts.MessageFact,
    request_id: str,
) -> EventDraft:
    activity = leaf.activity_ref.activity_id
    adoption = saved_activity.identity.adoption_ref
    use = task_facts.TaskUseFact(
        task_use_id=UUID(card.part.task_use_ref.id),
        scope_id=scope,
        activity_id=activity,
        round_id=None,
        plan_item_ref=None,
        instance_ref=card.instance_ref,
        statement=card.part.statement.model_dump(mode="json"),
        adoption_ref=adoption,
        purpose=card.part.purpose,
        method_conditions={
            "method_refs": [item.model_dump(mode="json") for item in card.method_refs]
        },
        prepared_at=message.committed_at,
        provided_message_ref=message.message_id,
    )
    return replace(
        draft(
            scope,
            task_facts.PRESENTED,
            card.part.task_use_ref,
            task_facts.TaskUseCreated(
                task_use_ref=card.part.task_use_ref,
                activity_ref=ref("activity", activity, leaf.activity_ref.revision),
                round_ref=None,
                plan_ref=None,
                adoption_ref=Ref(owner="product", type="space_adoption", id=str(adoption)),
                records=[facts.record(task_facts.TASK_USE, use.task_use_id, use)],
            ),
            request_id,
        ),
        causation_event_id=card.supply_event_id,
    )


async def request_question(
    conversation: Conversation,
    registry: Registry,
    activity_config: ActivityConfig,
    run: RunInput,
    question: TeachingQuestion,
    waits: Waits,
    domain_for: Callable[[AsyncConnection, UUID], Awaitable[UUID]],
) -> WaitCall | None:
    async with conversation.engine.connect() as db:
        work = await store.load(db, run.execution_id)
        active = (await history.current(db, work.scope_id)).current_activity
        # 仅讲解与答疑类活动可发起例题/练习供题。
        if active is None or active.type not in {"explanation", "question_answer"}:
            return None
        state = await history.activity_at(db, work.scope_id, active.activity_ref.activity_id)
    config, course = await activity_config(
        work.scope_id, state.identity.adoption_ref, active.type, state.identity.config_ref
    )
    # 当前蓝图节点须授权 reply，才允许出题。
    if config is None or not any(
        node.node_id == active.node_id and "reply" in node.allowed_actions
        for node in config.definition.blueprint.nodes
    ):
        return None
    async with conversation.engine.begin() as db:
        work = await store.active(db, registry, run, "step")
        leaf = (await history.current(db, work.scope_id)).current_activity
        # 事务内重新读叶活动，与初次判定不一致则中止，避免活动已切换。
        if leaf is None or active.activity_ref != leaf.activity_ref:
            return None
        principal = UUID((await store.authorization(db, run.execution_id)).initiator_ref.id)
        request_id = await db.scalar(
            text("SELECT request_id FROM interaction.inputs WHERE input_id=:id"),
            {"id": UUID(work.input_ref.id)},
        )
        if not isinstance(request_id, str):
            # 供题须挂在原始输入上，缺失请求编号则报错。
            raise ValueError("Question supply requires its original input")
        saved = await wait_for_question(
            db,
            conversation,
            waits,
            run,
            work,
            leaf,
            course,
            question,
            domain_for,
            principal,
            request_id,
        )
        # 等待已登记则返回等待调用，否则返回空。
        return WaitCall(run=run, wait_id=saved.wait_id) if saved else None
