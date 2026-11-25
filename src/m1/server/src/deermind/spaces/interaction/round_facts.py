"""正式检测轮及其结束原因沿事件追加。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    InlineContent,
    Ref,
    StoredEvent,
)
from deermind.foundation.system.projections.receipts import application
from deermind.spaces.interaction.conversation_facts import record as fact_record
from deermind.spaces.interaction.detection_plans import PROGRESS, PlanProgress
from deermind.spaces.interaction.public import DetectionPlanRef, DetectionRoundView
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

STARTED = "DetectionRoundStarted"
CLOSED = "DetectionRoundClosed"
ROUND = "interaction.detection_rounds"
REVISION = "interaction.round_revisions"


class Round(FactModel):
    round_id: UUID
    activity_id: UUID
    plan_id: UUID
    plan_revision: int
    item_id: str
    task_use_ref: UUID
    opened_at: datetime


class RoundRevision(FactModel):
    round_id: UUID
    revision: int
    state: Literal["open", "paused", "closed"]
    reason: str
    source_input_ref: UUID | None
    source_trigger_ref: UUID | None
    submission_ref: UUID | None
    created_at: datetime


class RoundStarted(EventPayload):
    round_ref: Ref
    activity_ref: Ref
    plan_ref: DetectionPlanRef
    task_use_ref: Ref
    source_input_ref: Ref


class RoundClosed(EventPayload):
    round_ref: Ref
    revision_ref: Ref
    reason: Literal["submitted", "help_requested", "finished"]
    submission_ref: Ref | None


def validate(draft: EventDraft, payload: EventPayload) -> None:
    # 开轮事件须为固定三记录顺序，且所有者与轮次引用一致。
    if (
        not isinstance(payload, RoundStarted)
        or [row.record_type for row in payload.records]
        != [
            ROUND,
            REVISION,
            PROGRESS,
        ]
        or draft.owner_ref != payload.round_ref
    ):
        raise ValueError("A started round must identify its fixed plan and opening record")
    for row in payload.records:
        if not isinstance(row.content, InlineContent):
            raise ValueError("Round data must be decoded")
    identity, revision, progress = [
        row.content.value for row in payload.records if isinstance(row.content, InlineContent)
    ]
    # 轮次、活动、任务使用、题单版本及修订状态、进度引用须与开轮事件吻合。
    if (
        identity["round_id"] != payload.round_ref.id
        or identity["activity_id"] != payload.activity_ref.id
        or identity["task_use_ref"] != payload.task_use_ref.id
        or identity["plan_id"] != str(payload.plan_ref.plan_id)
        or identity["plan_revision"] != payload.plan_ref.revision
        or revision["round_id"] != payload.round_ref.id
        or revision["state"] != "open"
        or progress["current_round_ref"] != payload.round_ref.id
        or progress["status"] != "confirmed"
    ):
        raise ValueError("Round records conflict with opening event")


START_REGISTRATION = EventRegistration(
    STARTED,
    1,
    "interaction",
    "learning_space",
    RoundStarted,
    validate,
    {(ROUND, 1): Round, (REVISION, 1): RoundRevision, (PROGRESS, 1): PlanProgress},
)


def validate_close(draft: EventDraft, payload: EventPayload) -> None:
    # 闭轮事件须为两记录顺序；提交原因才允许带提交引用，其余原因不得带。
    if (
        not isinstance(payload, RoundClosed)
        or draft.owner_ref != payload.revision_ref
        or [row.record_type for row in payload.records] != [REVISION, PROGRESS]
        or (payload.submission_ref is None) != (payload.reason != "submitted")
    ):
        raise ValueError("A closed round requires a reason and updated progress")
    revision, progress = (row.content for row in payload.records)
    if not isinstance(revision, InlineContent) or not isinstance(progress, InlineContent):
        raise ValueError("A round close requires decoded records")
    # 修订身份、版本、关闭状态、原因、提交引用及进度轮次须与闭轮事件一致。
    if (
        revision.value["round_id"] != payload.round_ref.id
        or revision.value["revision"] != payload.revision_ref.revision
        or revision.value["state"] != "closed"
        or revision.value["reason"] != payload.reason
        or revision.value["submission_ref"]
        != (payload.submission_ref.id if payload.submission_ref else None)
        or progress.value["current_round_ref"] is not None
    ):
        raise ValueError("Round close records conflict with the event")


CLOSE_REGISTRATION = EventRegistration(
    CLOSED,
    1,
    "interaction",
    "learning_space",
    RoundClosed,
    validate_close,
    {(REVISION, 1): RoundRevision, (PROGRESS, 1): PlanProgress},
)


async def close_payload(
    db: AsyncConnection,
    opened: DetectionRoundView,
    input_id: UUID,
    reason: Literal["submitted", "help_requested", "finished"],
    submission: Ref | None,
    now: datetime,
) -> tuple[RoundClosed, bool]:
    """取得同一题单剩余项，在对应业务事务中保存真实关闭原因。"""
    fixed = opened.plan_ref
    state = (
        await db.execute(
            text(
                "SELECT p.confirmed_by_input, "
                "(SELECT count(*) FROM interaction.detection_rounds r "
                "WHERE (r.plan_id,r.plan_revision)=(p.plan_id,p.plan_revision)) AS used, v.items "
                "FROM interaction.plan_progress p JOIN interaction.plan_revisions v "
                "ON (v.plan_id,v.revision)=(p.plan_id,p.plan_revision) "
                "WHERE p.plan_id=:id AND p.plan_revision=:version FOR UPDATE OF p"
            ),
            {"id": fixed.plan_id, "version": fixed.revision},
        )
    ).one()
    remaining = state.items[state.used :]
    # 尚有剩余项且为提交完成，题单继续；否则按原因收尾。
    continuing = bool(remaining) and reason == "submitted"
    # 非提交原因时，剩余项全部记为取消；提交完成则不产生取消项。
    cancelled = (
        [{"item_id": item["item_id"], "reason": reason} for item in remaining]
        if reason != "submitted"
        else []
    )
    progress = PlanProgress(
        plan_id=fixed.plan_id,
        plan_revision=fixed.revision,
        confirmed_by_input=state.confirmed_by_input,
        # 继续为 confirmed；提交完成且无剩余为 finished；其余原因整体 cancelled。
        status="confirmed" if continuing else "finished" if reason == "submitted" else "cancelled",
        cancelled_items=cancelled,
        current_round_ref=None,
    )
    round_ref = opened.round_ref
    assert round_ref.revision is not None
    revision = round_ref.model_copy(update={"revision": round_ref.revision + 1})
    saved = RoundRevision(
        round_id=UUID(round_ref.id),
        revision=round_ref.revision + 1,
        state="closed",
        reason=reason,
        source_input_ref=input_id,
        source_trigger_ref=None,
        submission_ref=UUID(submission.id) if submission else None,
        created_at=now,
    )
    body = RoundClosed(
        round_ref=round_ref,
        revision_ref=revision,
        reason=reason,
        submission_ref=submission,
        records=[
            fact_record(REVISION, f"{round_ref.id}:{saved.revision}", saved),
            fact_record(PROGRESS, f"{fixed.plan_id}:{fixed.revision}", progress),
        ],
    )
    return body, continuing


async def project(db: AsyncConnection, event: StoredEvent) -> None:
    async with application(db, "interaction.detection_rounds", 1, event.draft.event_id) as needed:
        # 事件已投影过，重复应用直接返回。
        if not needed:
            return
        for record in event.payload.records:
            if not isinstance(record.content, InlineContent):
                raise ValueError("Round projection requires decoded records")
            table = record.record_type
            body = {**record.content.value, "source_event_id": str(event.draft.event_id)}
            if table == PROGRESS:
                # 进度为更新既有行，走专门的进度投影。
                await project_progress(db, body)
            elif table in {ROUND, REVISION}:
                # 轮次与修订为追加事实行。
                await db.execute(
                    text(
                        f"INSERT INTO {table} SELECT * FROM "
                        f"jsonb_populate_record(NULL::{table}, CAST(:body AS jsonb))"
                    ),
                    {"body": canonical_json(body)},
                )
            else:
                # 其余表类型不在本轮投影范围，拒绝落表。
                raise ValueError("Unknown round projection record")


async def project_progress(db: AsyncConnection, body: dict[str, JsonValue]) -> None:
    await db.execute(
        text(
            "UPDATE interaction.plan_progress p SET status=x.status, "
            "confirmed_by_input=x.confirmed_by_input, "
            "current_round_ref=x.current_round_ref, "
            "source_event_id=x.source_event_id, cancelled_items=x.cancelled_items "
            "FROM jsonb_populate_record(NULL::interaction.plan_progress, "
            "CAST(:body AS jsonb)) x "
            "WHERE (p.plan_id,p.plan_revision)=(x.plan_id,x.plan_revision)"
        ),
        {"body": canonical_json(body)},
    )
