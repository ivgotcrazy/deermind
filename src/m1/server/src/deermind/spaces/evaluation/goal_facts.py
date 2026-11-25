"""Fixed input/result snapshots and the Evaluation-owned current-result projection."""

from datetime import datetime
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
from deermind.spaces.evaluation.public import GoalEvaluation
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

COMPLETED = "GoalEvaluationCompleted"
INPUT = "evaluation.goal_calculation_input"
RESULT = "evaluation.goal_evaluation"


class CalculationInput(FactModel):
    input_id: UUID
    scope_id: UUID
    trigger_event_id: UUID
    target_basis_ref: UUID
    adoption_ref: UUID
    mastery_snapshot_ref: UUID | None
    mastery_publication_seq: int
    evidence_coverage: list[JsonValue]
    calculation_rule_ref: str
    planned_result_id: UUID
    created_at: datetime


class GoalCompleted(EventPayload):
    trigger_event_id: UUID
    goal_evaluation_ref: Ref
    target_basis_ref: Ref
    snapshot_ref: Ref | None
    result_ref: Ref
    previous_current_ref: Ref | None
    current_state_applied: bool
    not_applied_reason: str | None


def validate(draft: EventDraft, payload: EventPayload) -> None:
    if not isinstance(payload, GoalCompleted):
        raise ValueError("Invalid goal result")
    records = {record.record_type: record for record in payload.records}
    # 一次目标评价必须同时携带计算输入与结果两条记录。
    if set(records) != {INPUT, RESULT} or len(payload.records) != 2:
        raise ValueError("A goal evaluation needs both its input and result")
    checked, result = records[INPUT].content, records[RESULT].content
    assert isinstance(checked, InlineContent) and isinstance(result, InlineContent)
    # 两条记录的范围、触发事件与目标依据须与事件正文一致。
    for row in (checked.value, result.value):
        if (
            row["scope_id"] != str(draft.scope_id)
            or row["trigger_event_id"] != str(payload.trigger_event_id)
            or row["target_basis_ref"] != payload.target_basis_ref.id
        ):
            raise ValueError("Goal evaluation references differ from its fixed input")
    # 结果标识、计划结果、输入引用与当前态标记须两条记录互相对得上。
    if (
        result.value["goal_evaluation_id"] != payload.goal_evaluation_ref.id
        or result.value["goal_evaluation_id"] != checked.value["planned_result_id"]
        or result.value["input_ref"] != checked.value["input_id"]
        or result.value["current_state_applied"] != payload.current_state_applied
    ):
        raise ValueError("Goal evaluation records disagree")


REGISTRATION = EventRegistration(
    COMPLETED,
    1,
    "evaluation",
    "learning_space",
    GoalCompleted,
    validate,
    {(INPUT, 1): CalculationInput, (RESULT, 1): GoalEvaluation},
)


async def project(connection: AsyncConnection, saved: StoredEvent) -> None:
    async with application(connection, "evaluation.goal_views", 1, saved.draft.event_id) as needed:
        # 事件已投影过，重复应用直接返回。
        if not needed:
            return
        records = {row.record_type: row.content for row in saved.payload.records}
        # 逐条把输入与结果记录落进对应投影表。
        for table in (INPUT, RESULT):
            record = records[table]
            assert isinstance(record, InlineContent)
            await connection.execute(
                text(
                    f"INSERT INTO {table} SELECT * FROM "
                    f"jsonb_populate_record(NULL::{table}, CAST(:body AS jsonb))"
                ),
                {
                    "body": canonical_json(
                        {
                            **record.value,
                            "source_event_id": str(saved.draft.event_id),
                        }
                    )
                },
            )
        payload = saved.payload
        assert isinstance(payload, GoalCompleted)
        # 仅当本次结果已应用为当前态时，更新范围当前结果指针。
        if payload.current_state_applied:
            fixed = records[INPUT]
            assert isinstance(fixed, InlineContent)
            await connection.execute(
                text(
                    "INSERT INTO evaluation.goal_current("
                    "scope_id,current_result_ref,target_basis_ref,mastery_publication_seq) "
                    "VALUES (:scope,:result,:basis,:seq) ON CONFLICT(scope_id) DO UPDATE "
                    "SET current_result_ref=EXCLUDED.current_result_ref,"
                    "target_basis_ref=EXCLUDED.target_basis_ref,"
                    "mastery_publication_seq=EXCLUDED.mastery_publication_seq"
                ),
                {
                    "scope": saved.draft.scope_id,
                    "result": UUID(payload.goal_evaluation_ref.id),
                    "basis": UUID(payload.target_basis_ref.id),
                    "seq": fixed.value["mastery_publication_seq"],
                },
            )
