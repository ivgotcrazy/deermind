"""活动和正式消息的事实合同。交互模块拥有投影与当前行更新。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

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
from deermind.foundation.system.projections.receipts import application
from deermind.spaces.interaction.public import (
    ActivityControlResult,
    ActivityRef,
    ActivityType,
    LearningInputAcceptance,
    LearningTurnResult,
    MessagePart,
    RunState,
)
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

INPUT = "interaction.inputs"
RESULT = "interaction.input_results"
MESSAGE = "interaction.messages"
ACTIVITY = "interaction.activities"
REVISION = "interaction.activity_revisions"
ASSIGNMENT = "interaction.message_assignments"
CONTEXT = "interaction.context_bundles"
DECISION = "interaction.decision_records"

ACCEPTED = "InteractionInputAccepted"
COMPLETED = "InteractionInputCompleted"
RECORDED = "ChatMessageRecorded"
CHANGED = "ActivityChanged"
ASSIGNED = "MessageAssigned"
CONTEXT_PREPARED = "InteractionContextPrepared"
DECISION_RECORDED = "InteractionDecisionRecorded"


def ref(kind: str, identity: UUID, revision: int | None = None) -> Ref:
    """返回不会随头修订变化的业务引用。"""
    return Ref(owner="interaction", type=kind, id=str(identity), revision=revision)


class InputFact(FactModel):
    input_id: UUID
    scope_id: UUID
    request_id: str
    kind: Literal["message", "answer", "activity_control", "stop"]
    input: dict[str, JsonValue]
    turn_epoch: int
    accepted_at: datetime


class InputResultFact(FactModel):
    result_id: UUID
    input_id: UUID
    step_key: str
    outcome: Literal["completed", "needs_input", "blocked", "failed", "cancelled"]
    message_refs: list[Ref]
    activity_revision_refs: list[Ref]
    error_ref: Ref | None
    created_at: datetime


class MessageFact(FactModel):
    message_id: UUID
    scope_id: UUID
    message_seq: int
    role: Literal["student", "assistant", "system"]
    parts: list[MessagePart]
    source_input_ref: UUID | None
    source_trigger_ref: UUID | None
    committed_at: datetime


class ActivityFact(FactModel):
    activity_id: UUID
    scope_id: UUID
    root_id: UUID
    parent_id: UUID | None
    type: ActivityType
    name: str
    config_ref: UUID
    adoption_ref: UUID
    started_at: datetime
    first_message_ref: UUID


class ReturnPoint(FactModel):
    parent: ActivityRef
    node_id: str


class RevisionFact(FactModel):
    activity_id: UUID
    revision: int
    node_id: str
    run_state: RunState
    return_point: ReturnPoint | None
    related_round_ref: Ref | None
    reason: str
    source_input_ref: UUID | None
    source_trigger_ref: UUID | None
    created_at: datetime


class AssignmentFact(FactModel):
    message_id: UUID
    activity_id: UUID
    assigned_by_input_ref: UUID | None
    source_trigger_ref: UUID | None
    created_at: datetime


class ContextFact(FactModel):
    bundle_id: UUID
    scope_id: UUID
    run_ref: UUID
    source_ref: Ref
    purpose: Literal["explanation", "question_answer"]
    activity_revision_ref: Ref | None
    adoption_ref: UUID
    config_ref: UUID
    materials: list[dict[str, JsonValue]]
    memory_refs: list[Ref]
    publication_refs: list[Ref]
    omissions: list[str]
    created_at: datetime


class DecisionFact(FactModel):
    decision_id: UUID
    scope_id: UUID
    input_ref: UUID
    source_trigger_ref: UUID | None
    activity_revision_ref: Ref | None
    context_bundle_id: UUID
    ai_candidate_ref: Ref
    proposal: dict[str, JsonValue]
    validation: dict[str, JsonValue]
    accepted_action: dict[str, JsonValue]
    created_at: datetime


class ContextPrepared(EventPayload):
    subject_ref: Ref
    outcome: Literal["recorded"] = "recorded"
    reason_code: None = None


class DecisionRecorded(EventPayload):
    subject_ref: Ref
    outcome: Literal["allowed", "denied", "clarify"]
    reason_code: str | None


class InputAccepted(EventPayload):
    input_ref: Ref
    adoption_ref: Ref
    acceptance: LearningInputAcceptance | None = None


class InputCompleted(EventPayload):
    input_ref: Ref
    result_ref: Ref
    control_result: ActivityControlResult | None = None
    turn_result: LearningTurnResult | None = None


class MessageRecorded(EventPayload):
    message_ref: Ref
    activity_ref: Ref | None
    source_input_ref: Ref | None
    source_trigger_ref: Ref | None
    role: Literal["student", "assistant", "system"]


class ActivityChanged(EventPayload):
    activity_ref: Ref
    revision_ref: Ref
    parent_ref: Ref | None
    node_id: str
    reason: str
    source_input_ref: Ref | None
    source_trigger_ref: Ref | None


class MessageAssigned(EventPayload):
    message_ref: Ref
    activity_ref: Ref


MODELS: dict[str, type[FactModel]] = {
    INPUT: InputFact,
    RESULT: InputResultFact,
    MESSAGE: MessageFact,
    ACTIVITY: ActivityFact,
    REVISION: RevisionFact,
    ASSIGNMENT: AssignmentFact,
    CONTEXT: ContextFact,
    DECISION: DecisionFact,
}


def record(table: str, key: UUID | str, value: FactModel) -> FactRecord:
    """生成固定记录，保留业务身份。"""
    return FactRecord(
        record_id=str(key),
        record_type=table,
        schema_version=1,
        content=InlineContent(storage="inline", value=value.model_dump(mode="json")),
    )


def validate(draft: EventDraft, payload: EventPayload) -> None:
    """验明每条记录的空间、业务身份以及本事件携带的记录组合。"""
    expected: dict[str, tuple[Ref, str]] = {}
    if isinstance(payload, InputAccepted):
        expected[INPUT] = (payload.input_ref, "input_id")
    elif isinstance(payload, InputCompleted):
        expected[RESULT] = (payload.result_ref, "result_id")
    elif isinstance(payload, MessageRecorded):
        expected[MESSAGE] = (payload.message_ref, "message_id")
    elif isinstance(payload, ActivityChanged):
        expected[REVISION] = (payload.revision_ref, "activity_id")
        if payload.revision_ref.revision == 1:
            expected[ACTIVITY] = (payload.activity_ref, "activity_id")
    elif isinstance(payload, MessageAssigned):
        expected[ASSIGNMENT] = (payload.message_ref, "message_id")
    elif isinstance(payload, ContextPrepared) and payload.subject_ref == draft.owner_ref:
        expected[CONTEXT] = (payload.subject_ref, "bundle_id")
    elif isinstance(payload, DecisionRecorded) and payload.subject_ref == draft.owner_ref:
        expected[DECISION] = (payload.subject_ref, "decision_id")
    else:
        raise ValueError("Unexpected interaction event")
    if {item.record_type for item in payload.records} != expected.keys() or len(
        payload.records
    ) != len(expected):
        raise ValueError("Unexpected interaction records")
    for item in payload.records:
        content = item.content
        identity, column = expected[item.record_type]
        if not isinstance(content, InlineContent) or (
            content.value[column] != identity.id
            or content.value.get("scope_id", str(draft.scope_id)) != str(draft.scope_id)
            or (
                item.record_type == REVISION
                and isinstance(payload, ActivityChanged)
                and (
                    content.value["revision"] != payload.revision_ref.revision
                    or content.value["node_id"] != payload.node_id
                )
            )
        ):
            raise ValueError("Interaction record identity differs from payload")


REGISTRATIONS = [
    EventRegistration(
        event,
        1,
        "interaction",
        "learning_space",
        model,
        validate,
        {(table, 1): MODELS[table] for table in tables},
    )
    for event, model, tables in (
        (ACCEPTED, InputAccepted, (INPUT,)),
        (COMPLETED, InputCompleted, (RESULT,)),
        (RECORDED, MessageRecorded, (MESSAGE,)),
        (CHANGED, ActivityChanged, (ACTIVITY, REVISION)),
        (ASSIGNED, MessageAssigned, (ASSIGNMENT,)),
        (CONTEXT_PREPARED, ContextPrepared, (CONTEXT,)),
        (DECISION_RECORDED, DecisionRecorded, (DECISION,)),
    )
]


async def project(connection: AsyncConnection, saved: StoredEvent) -> None:
    """幂等地写入事实行，并更新其派生指针。"""
    async with application(
        connection, "interaction.conversation", 1, saved.draft.event_id
    ) as needed:
        if not needed:
            return
        for item in saved.payload.records:
            body = item.content
            table = item.record_type
            if table not in MODELS or not isinstance(body, InlineContent):
                raise ValueError("Unexpected interaction projection")
            await connection.execute(
                text(
                    f"INSERT INTO {table} SELECT * FROM "
                    f"jsonb_populate_record(NULL::{table},CAST(:body AS jsonb))"
                ),
                {
                    "body": canonical_json(
                        {**body.value, "source_event_id": str(saved.draft.event_id)}
                    )
                },
            )
            if table == REVISION:
                await connection.execute(
                    text(
                        "INSERT INTO interaction.activity_heads(activity_id,revision) "
                        "VALUES (:id,:revision) ON CONFLICT(activity_id) "
                        "DO UPDATE SET revision=EXCLUDED.revision"
                    ),
                    {
                        "id": UUID(str(body.value["activity_id"])),
                        "revision": body.value["revision"],
                    },
                )
