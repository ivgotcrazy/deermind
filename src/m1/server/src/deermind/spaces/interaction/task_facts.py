"""正式呈现、作答和判题各自保存原始事实。"""

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
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

PRESENTED = "TaskUseCreated"
SUBMITTED = "AnswerSubmitted"
FEEDBACK = "AnswerFeedbackPrepared"
TASK_USE = "interaction.task_uses"
SUBMISSION = "interaction.submissions"
ANSWER_FEEDBACK = "interaction.answer_feedback"


class TaskUseFact(FactModel):
    task_use_id: UUID
    scope_id: UUID
    activity_id: UUID
    round_id: UUID | None
    plan_item_ref: Ref | None
    instance_ref: Ref | None
    statement: dict[str, JsonValue]
    adoption_ref: UUID
    purpose: Literal["example", "practice", "detection", "student_question"]
    method_conditions: dict[str, JsonValue]
    prepared_at: datetime
    provided_message_ref: UUID


class SubmissionFact(FactModel):
    submission_id: UUID
    scope_id: UUID
    source_input_ref: UUID
    task_use_ref: UUID
    activity_id: UUID
    round_id: UUID | None
    answer: dict[str, JsonValue]
    help_basis: dict[str, JsonValue]
    adoption_ref: UUID
    accepted_at: datetime
    event_ref: UUID


class AnswerFeedbackFact(FactModel):
    feedback_id: UUID
    submission_id: UUID
    verdict: Literal["correct", "incorrect", "partial", "uncertain"]
    basis_refs: list[Ref]
    feedback: dict[str, JsonValue]
    limitations: list[str]
    run_ref: UUID
    created_at: datetime


class TaskUseCreated(EventPayload):
    task_use_ref: Ref
    activity_ref: Ref
    round_ref: Ref | None
    plan_ref: Ref | None
    adoption_ref: Ref


class AnswerSubmitted(EventPayload):
    submission_ref: Ref
    task_use_ref: Ref
    activity_ref: Ref
    round_ref: Ref | None
    plan_ref: Ref | None
    adoption_ref: Ref
    help_basis_ref: Ref


class AnswerFeedbackPrepared(EventPayload):
    feedback_ref: Ref
    submission_ref: Ref
    source_input_ref: Ref


def validate(draft: EventDraft, payload: EventPayload) -> None:
    # 任务事件只携带一条已解码的内联记录。
    if len(payload.records) != 1 or not isinstance(payload.records[0].content, InlineContent):
        raise ValueError("A task event requires one decoded record")
    body = payload.records[0].content.value
    if isinstance(payload, TaskUseCreated):
        expected = {
            "task_use_id": payload.task_use_ref.id,
            "scope_id": str(draft.scope_id),
            "activity_id": payload.activity_ref.id,
            "adoption_ref": payload.adoption_ref.id,
            "round_id": payload.round_ref.id if payload.round_ref else None,
        }
        subject = payload.task_use_ref
    elif isinstance(payload, AnswerSubmitted):
        expected = {
            "submission_id": payload.submission_ref.id,
            "scope_id": str(draft.scope_id),
            "task_use_ref": payload.task_use_ref.id,
            "activity_id": payload.activity_ref.id,
            "round_id": payload.round_ref.id if payload.round_ref else None,
            "adoption_ref": payload.adoption_ref.id,
            "event_ref": str(draft.event_id),
        }
        subject = payload.submission_ref
    elif isinstance(payload, AnswerFeedbackPrepared):
        expected = {
            "feedback_id": payload.feedback_ref.id,
            "submission_id": payload.submission_ref.id,
        }
        subject = payload.feedback_ref
    else:
        raise ValueError("Unregistered interaction task fact")
    # 草稿所有者、记录标识与正文各身份字段须与事件引用逐项一致。
    if (
        draft.owner_ref != subject
        or payload.records[0].record_id != subject.id
        or any(body[key] != value for key, value in expected.items())
    ):
        raise ValueError("Task fact does not match its event")


REGISTRATIONS = [
    EventRegistration(
        kind, 1, "interaction", "learning_space", payload, validate, {(table, 1): body}
    )
    for kind, payload, table, body in (
        (PRESENTED, TaskUseCreated, TASK_USE, TaskUseFact),
        (SUBMITTED, AnswerSubmitted, SUBMISSION, SubmissionFact),
        (FEEDBACK, AnswerFeedbackPrepared, ANSWER_FEEDBACK, AnswerFeedbackFact),
    )
]


async def project(db: AsyncConnection, event: StoredEvent) -> None:
    async with application(db, "interaction.task_uses", 1, event.draft.event_id) as needed:
        # 事件已投影过，重复应用直接返回。
        if not needed:
            return
        record = event.payload.records[0]
        table = record.record_type
        # 表类型须在三类任务事实内，且正文为已解码内联内容。
        if table not in {TASK_USE, SUBMISSION, ANSWER_FEEDBACK} or not isinstance(
            record.content, InlineContent
        ):
            raise ValueError("Unexpected task projection")
        await db.execute(
            text(
                f"INSERT INTO {table} SELECT * FROM "
                f"jsonb_populate_record(NULL::{table}, CAST(:body AS jsonb))"
            ),
            {
                "body": canonical_json(
                    {**record.content.value, "source_event_id": str(event.draft.event_id)}
                )
            },
        )
