"""Claim 的完整事件正文和所属投影。"""

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
from deermind.foundation.system.public.errors import Issue
from deermind.spaces.domain.public import SolutionRef, TaskRef
from deermind.spaces.evaluation.public import ClaimDefinition, ClaimRef
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

EVENT = "ClaimDefinitionChanged"
RECORD = "evaluation.claim_version"
RECORD_ID = "claim-version"


class ClaimVersion(FactModel):
    claim_id: UUID
    revision: int
    definition: ClaimDefinition
    gaps: list[Issue]
    request_ref: str
    actor_ref: Ref
    created_at: datetime


class ClaimChanged(EventPayload):
    domain_id: UUID
    task_ref: TaskRef
    previous_claim_ref: ClaimRef | None
    claim_ref: ClaimRef
    action: str
    affected_method_refs: list[SolutionRef]
    affected_criterion_ids: list[UUID]
    request_ref: UUID


def validate(draft: EventDraft, payload: EventPayload) -> None:
    # 变更事件恰好携带一条版本记录。
    if not isinstance(payload, ClaimChanged) or len(payload.records) != 1:
        raise ValueError("Claim change must carry a complete version")
    item = payload.records[0]
    # 记录编号、类型与内联正文不符，判版本记录无效。
    if (
        item.record_id != RECORD_ID
        or item.record_type != RECORD
        or not isinstance(item.content, InlineContent)
    ):
        raise ValueError("Claim change record is invalid")
    version = ClaimVersion.model_validate_json(canonical_json(item.content.value))
    # 范围、领域、任务、主张标识与请求引用必须与事件正文逐项一致。
    if (
        draft.scope_id != payload.domain_id
        or version.definition.domain_id != payload.domain_id
        or version.definition.task_ref != payload.task_ref
        or (version.claim_id, version.revision)
        != (payload.claim_ref.claim_id, payload.claim_ref.revision)
        or version.request_ref != str(payload.request_ref)
    ):
        raise ValueError("Claim change does not identify its own version")


REGISTRATION = EventRegistration(
    EVENT, 1, "evaluation", "domain", ClaimChanged, validate, {(RECORD, 1): ClaimVersion}
)


async def project(connection: AsyncConnection, event: StoredEvent) -> None:
    payload = event.payload
    assert isinstance(payload, ClaimChanged)
    item = payload.records[0].content
    assert isinstance(item, InlineContent)
    version = ClaimVersion.model_validate_json(canonical_json(item.value))
    async with application(
        connection, "evaluation.claim_definitions", 1, event.draft.event_id
    ) as needed:
        # 事件已投影过，重复应用直接返回。
        if not needed:
            return
        await connection.execute(
            text(
                "INSERT INTO evaluation.claim "
                "(claim_id,domain_id,task_id,task_version,head_revision,created_at) "
                "VALUES (:id,:domain,:task,:version,:revision,:created) ON CONFLICT(claim_id) "
                "DO UPDATE SET head_revision=EXCLUDED.head_revision"
            ),
            {
                "id": version.claim_id,
                "domain": payload.domain_id,
                "task": payload.task_ref.object_id,
                "version": payload.task_ref.version,
                "revision": version.revision,
                "created": version.created_at,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO evaluation.claim_version SELECT * FROM "
                "jsonb_populate_record(NULL::evaluation.claim_version,CAST(:body AS jsonb))"
            ),
            {"body": canonical_json({**item.value, "source_event_id": str(event.draft.event_id)})},
        )
