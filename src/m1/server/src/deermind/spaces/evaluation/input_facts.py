"""有界评价输入的原始记录及投影。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
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
from deermind.spaces.domain.public import SolutionRef, TaskRef
from deermind.spaces.evaluation.public import ClaimRef
from deermind.spaces.interaction.public import EvaluationMaterialRole
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

PREPARED = "EvaluationInputPrepared"
INPUT = "evaluation.evaluation_input"


class MaterialLocator(FactModel):
    role: EvaluationMaterialRole
    ref: EventPartRef
    sha256: str


class DomainLocator(FactModel):
    ref: Ref
    source_event_id: UUID
    sha256: str


class CandidateMethod(FactModel):
    method_ref: SolutionRef
    chapter_sources: list[Ref]


class CandidateTask(FactModel):
    task_ref: TaskRef
    claim_ref: ClaimRef
    methods: list[CandidateMethod]
    gaps: list[str]


class EvaluationInput(FactModel):
    adoption_ref: Ref
    application_ref: Ref
    target_basis_ref: Ref
    activity_ref: Ref
    task_use_ref: Ref | None
    round_ref: Ref | None
    plan_ref: Ref | None
    task_instance_ref: Ref | None
    occurred_at: datetime
    candidate_scope: list[CandidateTask]
    materials: list[MaterialLocator]
    domain_materials: list[DomainLocator]
    history_basis: list[EventPartRef]
    missing_reasons: list[str]
    interpretation_contract_ref: str
    parameter_ref: str
    algorithm_ref: str


class InputRecord(FactModel):
    input_id: UUID
    scope_id: UUID
    trigger_event_id: UUID
    source_seq: int
    source_kind: Literal["answer", "teaching"]
    source_id: UUID
    input: EvaluationInput
    created_at: datetime


class InputPrepared(EventPayload):
    evaluation_input_ref: Ref
    trigger_event_id: UUID


def validate(draft: EventDraft, payload: EventPayload) -> None:
    # 正文类型、所有者引用、触发事件与记录基数须一致。
    if (
        not isinstance(payload, InputPrepared)
        or draft.owner_ref != payload.evaluation_input_ref
        or draft.causation_event_id != payload.trigger_event_id
        or len(payload.records) != 1
    ):
        raise ValueError("Evaluation input event has inconsistent identity")
    record = payload.records[0]
    # 记录类型与内联正文不符，判输入记录不完整。
    if record.record_type != INPUT or not isinstance(record.content, InlineContent):
        raise ValueError("Evaluation input requires its complete record")
    body = InputRecord.model_validate_json(canonical_json(record.content.value))
    # 输入标识、所有者、范围、触发事件与源序号必须与事件逐项对得上。
    if (
        str(body.input_id) != record.record_id
        or record.record_id != draft.owner_ref.id
        or body.scope_id != draft.scope_id
        or body.trigger_event_id != payload.trigger_event_id
        or body.source_seq < 1
    ):
        raise ValueError("Evaluation input record does not match its event")


REGISTRATION = EventRegistration(
    PREPARED, 1, "evaluation", "learning_space", InputPrepared, validate, {(INPUT, 1): InputRecord}
)


async def project(db: AsyncConnection, event: StoredEvent) -> None:
    async with application(db, INPUT, 1, event.draft.event_id) as needed:
        # 事件已投影过，重复应用直接返回。
        if not needed:
            return
        body = event.payload.records[0].content
        # 投影前正文仍须是已解码内联内容。
        if not isinstance(body, InlineContent):
            raise ValueError("Evaluation input is not decoded")
        await db.execute(
            text(
                "INSERT INTO evaluation.evaluation_input SELECT * FROM "
                "jsonb_populate_record(NULL::evaluation.evaluation_input, CAST(:body AS jsonb))"
            ),
            {"body": canonical_json({**body.value, "source_event_id": str(event.draft.event_id)})},
        )
