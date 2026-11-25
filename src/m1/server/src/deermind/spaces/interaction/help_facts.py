"""求助分类和正式帮助由 Interaction 追加与投影。"""

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
from deermind.spaces.interaction import round_facts
from deermind.spaces.interaction.conversation_facts import record
from deermind.spaces.interaction.detection_plans import PROGRESS, PlanProgress
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

HANDLED = "HelpHandled"
HELP = "interaction.help_facts"
Stage = Literal["handled", "provided"]
Classification = Literal["neutral", "substantive", "uncertain"]


class HelpFact(FactModel):
    help_id: UUID
    stage: Stage
    scope_id: UUID
    source_input_ref: UUID
    activity_id: UUID
    task_use_id: UUID | None
    classification: Classification
    reason: str
    round_closure_ref: Ref | None
    provided_part_refs: list[Ref]
    created_at: datetime


class HelpHandled(EventPayload):
    help_ref: Ref
    stage: Stage
    source_input_ref: Ref
    classification: Classification
    round_closure_ref: Ref | None
    provided_message_ref: Ref | None


def payload(
    saved: HelpFact,
    input_ref: Ref,
    message: Ref | None = None,
    progress: PlanProgress | None = None,
) -> HelpHandled:
    owner = Ref(owner="interaction", type="help", id=str(saved.help_id))
    records = [record(HELP, f"{saved.help_id}:{saved.stage}", saved)]
    # 附带计划进度时追加第二条进度记录。
    if progress is not None:
        records.append(record(PROGRESS, f"{progress.plan_id}:{progress.plan_revision}", progress))
    return HelpHandled(
        help_ref=owner,
        stage=saved.stage,
        source_input_ref=input_ref,
        classification=saved.classification,
        round_closure_ref=saved.round_closure_ref,
        provided_message_ref=message,
        records=records,
    )


def validate(draft: EventDraft, body: EventPayload) -> None:
    # 求助事件携带一条或两条记录。
    if not isinstance(body, HelpHandled) or len(body.records) not in {1, 2}:
        raise ValueError("A help event requires one record")
    item = body.records[0]
    if item.record_type != HELP or not isinstance(item.content, InlineContent):
        raise ValueError("Missing help record")
    saved = HelpFact.model_validate_json(canonical_json(item.content.value))
    # 范围、标识、阶段、分类、闭环引用须与事件正文一致；提供阶段须有对应引用，实质帮助须挂闭环。
    if (
        saved.scope_id != draft.scope_id
        or str(saved.help_id) != body.help_ref.id
        or str(saved.source_input_ref) != body.source_input_ref.id
        or saved.stage != body.stage
        or saved.classification != body.classification
        or saved.round_closure_ref != body.round_closure_ref
        or (saved.stage == "provided") != bool(saved.provided_part_refs)
        or (saved.stage == "provided") != bool(body.provided_message_ref)
        or (saved.classification == "substantive" and saved.round_closure_ref is None)
    ):
        raise ValueError("Inconsistent help record")
    # 第二条记录为计划取消进度，须满足已受理、实质分类、已取消且无当前轮。
    if len(body.records) == 2:
        progress = body.records[1]
        if (
            saved.stage != "handled"
            or saved.classification != "substantive"
            or progress.record_type != PROGRESS
            or not isinstance(progress.content, InlineContent)
            or progress.content.value["status"] != "cancelled"
            or progress.content.value["current_round_ref"] is not None
        ):
            raise ValueError("Invalid help plan cancellation")


REGISTRATION = EventRegistration(
    HANDLED,
    1,
    "interaction",
    "learning_space",
    HelpHandled,
    validate,
    {(HELP, 1): HelpFact, (PROGRESS, 1): PlanProgress},
)


async def answer_basis(
    db: AsyncConnection,
    scope: UUID,
    task: UUID,
    event: UUID,
    mode: Literal["practice", "detection"],
) -> dict[str, JsonValue]:
    """提交时固定已经保存的求助和接触事实；外部帮助未知。"""
    help_events = await db.scalars(
        text(
            "SELECT source_event_id FROM interaction.help_facts "
            "WHERE scope_id=:scope AND task_use_id=:id ORDER BY created_at,stage,help_id"
        ),
        {"scope": scope, "id": task},
    )
    previous_uses = await db.scalars(
        text(
            "SELECT prior.source_event_id FROM interaction.task_uses prior "
            "JOIN interaction.task_uses used ON used.scope_id=prior.scope_id "
            "AND used.instance_ref=prior.instance_ref "
            "WHERE used.scope_id=:scope AND used.task_use_id=:id AND prior.task_use_id<>:id "
            "AND prior.provided_message_ref IS NOT NULL "
            "ORDER BY prior.prepared_at,prior.task_use_id"
        ),
        {"scope": scope, "id": task},
    )
    return {
        "mode": mode,
        "task_use_event_id": str(event),
        "help_event_ids": [str(identity) for identity in help_events],
        "prior_task_use_event_ids": [str(identity) for identity in previous_uses],
        "external_help": "unknown",
    }


async def project(db: AsyncConnection, event: StoredEvent) -> None:
    async with application(db, "interaction.help", 1, event.draft.event_id) as apply:
        # 事件已投影过，重复应用直接返回。
        if not apply:
            return
        item = event.payload.records[0]
        if not isinstance(item.content, InlineContent):
            raise ValueError("Missing help record")
        await db.execute(
            text(
                "INSERT INTO interaction.help_facts SELECT * FROM "
                "jsonb_populate_record(NULL::interaction.help_facts,CAST(:body AS jsonb))"
            ),
            {
                "body": canonical_json(
                    {**item.content.value, "source_event_id": str(event.draft.event_id)}
                )
            },
        )
        # 存在第二条记录时，校验并投影计划取消进度。
        if len(event.payload.records) == 2:
            progress = event.payload.records[1].content
            if not isinstance(progress, InlineContent):
                raise ValueError("Missing cancelled plan progress")
            await round_facts.project_progress(
                db, {**progress.value, "source_event_id": str(event.draft.event_id)}
            )
