"""检测题单使用固定目标和章节方法来源，准备阶段不出题。"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid5

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    FactRecord,
    InlineContent,
    Ref,
    StoredEvent,
)
from deermind.abstractions.executions import Execution, RunInput
from deermind.abstractions.task_supply import COMPLETED, SuppliedTask, TaskSupplyRequested
from deermind.abstractions.waits import Condition, WaitCall
from deermind.foundation.system.projections.receipts import application
from deermind.foundation.system.waits.service import Waits
from deermind.product.public.courses import CourseSnapshot
from deermind.spaces.domain.public import SolutionRef, TaskRef
from deermind.spaces.evaluation.public import ClaimRef
from deermind.spaces.interaction.supply_wait import PROBE
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

PREPARED = "DetectionPlanPrepared"
PLAN = "interaction.detection_plans"
REVISION = "interaction.plan_revisions"
PROGRESS = "interaction.plan_progress"


class PlanRef(FactModel):
    plan_id: UUID
    revision: int


class PlanRequirement(FactModel):
    key: str
    task_ref: TaskRef
    methods: list[SolutionRef]
    sources: list[Ref]
    assessment_constraints: str | None
    aspects: list[str]


class PlanItem(FactModel):
    item_id: str
    title: str
    requirement: PlanRequirement
    supplied: SuppliedTask


class PlanWait(FactModel):
    requirement: PlanRequirement
    trigger: UUID
    waiting: WaitCall


class PlanIdentity(FactModel):
    plan_id: UUID
    activity_id: UUID
    scope_id: UUID
    created_at: datetime


class PlanRevision(FactModel):
    plan_id: UUID
    revision: int
    adoption_ref: UUID
    purpose: str
    items: list[PlanItem]
    coverage: dict[str, JsonValue]
    gaps: list[str]
    feedback_policy: dict[str, JsonValue]
    created_at: datetime


class PlanProgress(FactModel):
    plan_id: UUID
    plan_revision: int
    confirmed_by_input: UUID | None
    status: Literal["prepared", "confirmed", "finished", "cancelled", "superseded"]
    cancelled_items: list[dict[str, JsonValue]]
    current_round_ref: UUID | None


class PlanPrepared(EventPayload):
    plan_ref: PlanRef
    activity_ref: Ref
    coverage_ref: Ref
    source_input_ref: Ref


def prepared_plan(
    work: Execution,
    activity_ref: Ref,
    adoption: UUID,
    items: list[PlanItem],
    gaps: list[str],
) -> tuple[Ref, PlanPrepared]:
    """学生确认前的持久记录不带作答、评分和当前轮。"""
    plan_id = uuid5(work.execution_id, "detection-plan")
    owner = Ref(owner="interaction", type="detection_plan", id=str(plan_id), revision=1)
    now = datetime.now(UTC)
    identity = PlanIdentity(
        plan_id=plan_id,
        activity_id=UUID(activity_ref.id),
        scope_id=work.scope_id,
        created_at=now,
    )
    revision = PlanRevision(
        plan_id=plan_id,
        revision=1,
        adoption_ref=adoption,
        purpose="learning_target_check",
        items=items,
        coverage={"planned_method_checks": len(items)},
        gaps=gaps,
        feedback_policy={"individual_rounds": True, "show_reference_after_round": False},
        created_at=now,
    )
    progress = PlanProgress(
        plan_id=plan_id,
        plan_revision=1,
        status="prepared",
        confirmed_by_input=None,
        cancelled_items=[],
        current_round_ref=None,
    )
    records = [
        FactRecord(
            record_type=table,
            record_id=f"{plan_id}:{number}",
            schema_version=1,
            content=InlineContent(storage="inline", value=value.model_dump(mode="json")),
        )
        for number, (table, value) in enumerate(
            ((PLAN, identity), (REVISION, revision), (PROGRESS, progress))
        )
    ]
    return owner, PlanPrepared(
        plan_ref=PlanRef(plan_id=plan_id, revision=1),
        activity_ref=activity_ref,
        source_input_ref=work.input_ref,
        coverage_ref=owner.model_copy(update={"path": "/coverage"}),
        records=records,
    )


def validate(draft: EventDraft, payload: EventPayload) -> None:
    # 题单准备事件须为身份、内容、进度三记录固定顺序。
    if not isinstance(payload, PlanPrepared) or [row.record_type for row in payload.records] != [
        PLAN,
        REVISION,
        PROGRESS,
    ]:
        raise ValueError("A prepared plan requires its identity, content and progress")
    identity = str(payload.plan_ref.plan_id)
    for row in payload.records:
        # 各记录须为内联内容且共用同一题单标识。
        if not isinstance(row.content, InlineContent) or row.content.value["plan_id"] != identity:
            raise ValueError("Plan records do not share an identity")
    progress = payload.records[2].content
    assert isinstance(progress, InlineContent)
    # 所有者须匹配；准备阶段状态为 prepared 且不得悬挂当前轮次。
    if (
        draft.owner_ref.id != identity
        or progress.value["status"] != "prepared"
        or progress.value["current_round_ref"] is not None
    ):
        raise ValueError("A prepared plan cannot open a round")


REGISTRATION = EventRegistration(
    PREPARED,
    1,
    "interaction",
    "learning_space",
    PlanPrepared,
    validate,
    {(PLAN, 1): PlanIdentity, (REVISION, 1): PlanRevision, (PROGRESS, 1): PlanProgress},
)


async def project(db: AsyncConnection, event: StoredEvent) -> None:
    async with application(db, "interaction.detection_plans", 1, event.draft.event_id) as apply:
        # 事件已投影过，重复应用直接返回。
        if not apply:
            return
        for row in event.payload.records:
            # 表类型须属于三类题单记录，且正文为已解码内联内容。
            if row.record_type not in {PLAN, REVISION, PROGRESS} or not isinstance(
                row.content, InlineContent
            ):
                raise ValueError("Unknown plan record")
            table = row.record_type
            await db.execute(
                text(
                    f"INSERT INTO {table} SELECT * FROM "
                    f"jsonb_populate_record(NULL::{table},CAST(:body AS jsonb))"
                ),
                {
                    "body": canonical_json(
                        {**row.content.value, "source_event_id": str(event.draft.event_id)}
                    )
                },
            )


@dataclass(frozen=True)
class PlanRequirements:
    items: list[PlanRequirement]
    gaps: list[str]


def requirements(
    course: CourseSnapshot, claim_tasks: Mapping[ClaimRef, TaskRef]
) -> PlanRequirements:
    """每个目标要求按采用的方法拆分，记录哪些部分缺少合法来源。"""
    items: list[PlanRequirement] = []
    gaps: list[str] = []
    for goal in course.items:
        task = claim_tasks.get(goal.claim_ref)
        if task is None:
            # 目标缺少对应任务定义，记入缺口。
            gaps.append(goal.title + "缺少可用的任务定义。")
            continue
        eligible: list[tuple[SolutionRef, list[Ref], list[str]]] = []
        for condition in goal.methods:
            chapters = set(goal.chapter_refs).intersection(condition.chapter_refs)
            sources = [
                adopted.association_ref
                for chapter in course.chapters
                if chapter.chapter_id in chapters
                for adopted in chapter.associations
                if adopted.active
                and adopted.task_ref == task
                and condition.method_ref in adopted.method_refs
            ]
            if not sources:
                # 该方法在当前章节下没有有效采用来源，记入缺口。
                gaps.append(goal.title + "有方法缺少采用来源。")
                continue
            aspects = sorted({value.aspect_ref.aspect_code for value in condition.aspects})
            eligible.append((condition.method_ref, sources, aspects))
        # 任选其一模式：存在可用方法时合并为单条要求。
        if goal.method_mode == "any_one" and eligible:
            items.append(
                PlanRequirement(
                    key=str(goal.item_id),
                    task_ref=task,
                    methods=[item[0] for item in eligible],
                    sources=list(
                        dict.fromkeys(source for _, sources, _ in eligible for source in sources)
                    ),
                    assessment_constraints=goal.task_conditions.description or None,
                    aspects=sorted({aspect for _, _, aspects in eligible for aspect in aspects}),
                )
            )
        else:
            # 必选全部模式：每个可用方法各自拆成一条要求。
            for method, sources, aspects in eligible:
                items.append(
                    PlanRequirement(
                        key=f"{goal.item_id}:{method.object_id}:{method.version}",
                        task_ref=task,
                        methods=[method],
                        sources=sources,
                        assessment_constraints=goal.task_conditions.description or None,
                        aspects=aspects,
                    )
                )
    return PlanRequirements(items, gaps)


def supply_request(
    work: Execution,
    activity_ref: Ref,
    domain: UUID,
    item: PlanRequirement,
    exposure: list[Ref],
    exposed: list[Ref],
) -> tuple[UUID, TaskSupplyRequested]:
    trigger = uuid5(work.execution_id, "detection-supply:" + item.key)
    owner = Ref(owner="interaction", type="supply_request", id=str(trigger))
    payload = TaskSupplyRequested(
        request_ref=owner,
        supply_input_ref=work.input_ref,
        domain_id=domain,
        activity_ref=activity_ref,
        purpose="assessment",
        task_ref=Ref(
            owner="domain",
            type="task",
            id=str(item.task_ref.object_id),
            version=item.task_ref.version,
        ),
        allowed_method_refs=[
            Ref(owner="domain", type="solution", id=str(method.object_id), version=method.version)
            for method in item.methods
        ],
        assessment_constraints_ref=owner,
        assessment_constraints=item.assessment_constraints,
        method_source_refs=item.sources,
        exposure_refs=exposure,
        exposed_instances=exposed,
        count=1,
        records=[],
    )
    return trigger, payload


async def register_requirement(
    db: AsyncConnection,
    waits: Waits,
    run: RunInput,
    scope: UUID,
    trigger: UUID,
    requested: TaskSupplyRequested,
    requirement: PlanRequirement,
    now: datetime,
) -> PlanWait:
    wait = await waits.register(
        db,
        run,
        step_key="detection_supply:" + requirement.key,
        owner=requested.request_ref,
        condition=Condition(
            event_types=[COMPLETED],
            scope_kind="learning_space",
            scope_id=scope,
            equals={"producer": "domain", "correlation_id": str(trigger)},
        ),
        probe_ref=PROBE,
        deadline=min(now + timedelta(seconds=180), run.deadline_at - timedelta(seconds=20)),
        reserve_seconds=20,
    )
    return PlanWait(
        requirement=requirement, trigger=trigger, waiting=WaitCall(run=run, wait_id=wait.wait_id)
    )
