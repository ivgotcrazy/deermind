"""正式教学事实和客户端显示报告分别登记。"""

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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

STARTED = "TeachingOpportunityStarted"
CLOSED = "TeachingOpportunityClosed"
PRESENTED = "PresentationRecorded"
OPPORTUNITY = "interaction.teaching_opportunities"
CLOSURE = "interaction.opportunity_closures"
PRESENTATION = "interaction.presentations"
CloseReason = Literal["completed", "interrupted", "cancelled", "unable_to_continue"]
Surface = Literal["chat", "history", "textbook"]


class Opportunity(FactModel):
    opportunity_id: UUID
    scope_id: UUID
    activity_id: UUID
    adoption_ref: UUID
    purpose: str
    opened_by_input: UUID | None
    source_trigger_ref: UUID | None
    created_at: datetime


class Closure(FactModel):
    opportunity_id: UUID
    provided_part_refs: list[Ref]
    purpose: str
    close_reason: CloseReason
    closed_at: datetime
    source_input_ref: UUID | None
    source_trigger_ref: UUID | None
    event_ref: UUID


class Presentation(FactModel):
    presentation_id: UUID
    scope_id: UUID
    surface: Surface
    resource_ref: Ref
    part_refs: list[Ref]
    received_at: datetime
    client_reported_at: datetime | None


class OpportunityStarted(EventPayload):
    opportunity_ref: Ref
    activity_ref: Ref
    adoption_ref: Ref


class OpportunityClosed(EventPayload):
    opportunity_id: UUID
    closure_ref: Ref
    activity_ref: Ref
    adoption_ref: Ref
    provided_part_refs: list[Ref]
    purpose: str
    close_reason: CloseReason


class PresentationRecorded(EventPayload):
    presentation_ref: Ref
    surface: Surface
    resource_ref: Ref
    part_refs: list[Ref]


def validate(draft: EventDraft, body: EventPayload) -> None:
    if len(body.records) != 1:
        raise ValueError("One provision fact is required")
    item = body.records[0]
    if not isinstance(item.content, InlineContent):
        raise ValueError("Provision metadata must be inline")
    data = item.content.value
    if isinstance(body, OpportunityStarted):
        valid = (
            item.record_type == OPPORTUNITY
            and data["scope_id"] == str(draft.scope_id)
            and data["opportunity_id"] == body.opportunity_ref.id
            and data["activity_id"] == body.activity_ref.id
            and data["adoption_ref"] == body.adoption_ref.id
        )
    elif isinstance(body, OpportunityClosed):
        valid = (
            item.record_type == CLOSURE
            and data["opportunity_id"] == str(body.opportunity_id) == body.closure_ref.id
            and data["event_ref"] == str(draft.event_id)
            and data["close_reason"] == body.close_reason
            and data["purpose"] == body.purpose
            and bool(body.provided_part_refs)
            and data["provided_part_refs"]
            == [value.model_dump(mode="json") for value in body.provided_part_refs]
        )
    else:
        valid = (
            isinstance(body, PresentationRecorded)
            and item.record_type == PRESENTATION
            and data["scope_id"] == str(draft.scope_id)
            and data["presentation_id"] == body.presentation_ref.id
            and data["surface"] == body.surface
            and data["resource_ref"] == body.resource_ref.model_dump(mode="json")
            and data["part_refs"] == [value.model_dump(mode="json") for value in body.part_refs]
        )
    if not valid or len(item.record_id) == 0 or item.record_id != draft.owner_ref.id:
        raise ValueError("Inconsistent provision record")


REGISTRATIONS = (
    EventRegistration(
        STARTED,
        1,
        "interaction",
        "learning_space",
        OpportunityStarted,
        validate,
        {(OPPORTUNITY, 1): Opportunity},
    ),
    EventRegistration(
        CLOSED,
        1,
        "interaction",
        "learning_space",
        OpportunityClosed,
        validate,
        {(CLOSURE, 1): Closure},
    ),
    EventRegistration(
        PRESENTED,
        1,
        "interaction",
        "learning_space",
        PresentationRecorded,
        validate,
        {(PRESENTATION, 1): Presentation},
    ),
)
EVENTS = {row.event_type for row in REGISTRATIONS}


async def project(db: AsyncConnection, event: StoredEvent) -> None:
    async with application(db, "interaction.provision", 1, event.draft.event_id) as apply:
        if not apply:
            return
        item = event.payload.records[0]
        table = item.record_type
        if table not in {OPPORTUNITY, CLOSURE, PRESENTATION} or not isinstance(
            item.content, InlineContent
        ):
            raise ValueError("Unknown provision projection")
        await db.execute(
            text(
                f"INSERT INTO {table} SELECT * FROM "
                f"jsonb_populate_record(NULL::{table},CAST(:body AS jsonb))"
            ),
            {
                "body": canonical_json(
                    {**item.content.value, "source_event_id": str(event.draft.event_id)}
                )
            },
        )
