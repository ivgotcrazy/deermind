"""供题筛选依据和正式结果的事件记录。"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

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
from deermind.abstractions.task_supply import (
    COMPLETED,
    DomainTaskSupplyCompleted,
    SuppliedTask,
    UnfilledSupply,
)
from deermind.foundation.system.projections.receipts import application
from deermind.spaces.domain import analysis_facts

PREPARED = "DomainTaskSupplyPrepared"
CHECKED = "DomainTaskSupplyChecked"
BATCH = "domain.supply_batch"


class SupplyPrepared(EventPayload):
    trigger_event_id: UUID
    input_artifact_ref: Ref
    use_check_refs: list[Ref]


class SupplyBatch(FactModel):
    batch_id: UUID
    trigger_event_id: UUID
    scope_id: UUID
    input_artifact_id: UUID
    items: list[SuppliedTask]
    unfilled: list[UnfilledSupply]
    completed_event_id: UUID
    created_at: datetime


def _validate(draft: EventDraft, payload: EventPayload) -> None:
    if isinstance(payload, SupplyPrepared):
        refs = payload.use_check_refs
        if draft.event_type == PREPARED:
            refs = [payload.input_artifact_ref, *refs]
        if [record.record_id for record in payload.records] != [ref.id for ref in refs]:
            raise ValueError("Unexpected supply input or check records")
    elif isinstance(payload, DomainTaskSupplyCompleted):
        if (
            len(payload.records) != 1
            or payload.records[0].record_id != payload.supply_batch_ref.id
            or payload.supply_batch_ref != payload.result_ref
            or payload.supply_batch_ref != draft.owner_ref
        ):
            raise ValueError("Unexpected supply batch")
        record = payload.records[0].content
        if not isinstance(record, InlineContent) or (
            record.value["batch_id"] != payload.supply_batch_ref.id
            or record.value["scope_id"] != str(draft.scope_id)
            or record.value["trigger_event_id"] != str(payload.trigger_event_id)
            or record.value["completed_event_id"] != str(draft.event_id)
        ):
            raise ValueError("Supply batch does not match its source event")
    else:
        raise ValueError("Unexpected supply event")
    if draft.causation_event_id != payload.trigger_event_id:
        raise ValueError("Supply event must identify its original request")


REGISTRATIONS = [
    EventRegistration(
        PREPARED,
        1,
        "domain",
        "learning_space",
        SupplyPrepared,
        _validate,
        {(analysis_facts.ARTIFACT, 1): analysis_facts.AnalysisArtifact},
    ),
    EventRegistration(
        CHECKED,
        1,
        "domain",
        "learning_space",
        SupplyPrepared,
        _validate,
        {(analysis_facts.ARTIFACT, 1): analysis_facts.AnalysisArtifact},
    ),
    EventRegistration(
        COMPLETED,
        1,
        "domain",
        "learning_space",
        DomainTaskSupplyCompleted,
        _validate,
        {(BATCH, 1): SupplyBatch},
    ),
]


async def project(db: AsyncConnection, event: StoredEvent) -> None:
    async with application(db, "domain.task_supply", 1, event.draft.event_id) as needed:
        if needed:
            await _project(db, event)


async def _project(db: AsyncConnection, event: StoredEvent) -> None:
    for record in event.payload.records:
        if not isinstance(record.content, InlineContent):
            raise ValueError("Decoded supply record required")
        if record.record_type == analysis_facts.ARTIFACT:
            value = analysis_facts.AnalysisArtifact.model_validate_json(
                canonical_json(record.content.value)
            )
            await analysis_facts.project(db, event, value)
        elif record.record_type == BATCH:
            await db.execute(
                text(
                    "INSERT INTO domain.supply_batch SELECT * FROM "
                    "jsonb_populate_record(NULL::domain.supply_batch,CAST(:content AS jsonb))"
                ),
                {
                    "content": canonical_json(
                        {
                            **record.content.value,
                            "source_event_id": str(event.draft.event_id),
                        }
                    )
                },
            )
        else:
            raise ValueError("Unknown supply record format")
