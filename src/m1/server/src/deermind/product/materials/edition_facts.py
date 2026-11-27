"""Save the edition fact and its query projections in one transaction."""

from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    InlineContent,
    StoredEvent,
)
from deermind.foundation.system.projections.receipts import application
from deermind.product.public.material_editions import Edition
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

EVENT = "MaterialEditionSaved"
RECORD = "product.material_edition"


def validate(draft: EventDraft, payload: EventPayload) -> None:
    if len(payload.records) != 1:
        raise ValueError("Expected one textbook edition")
    record = payload.records[0]
    if not isinstance(record.content, InlineContent) or record.record_type != RECORD:
        raise ValueError("Incomplete textbook edition")
    body = record.content.value
    if (body["textbook_id"], body["edition_id"]) != (str(draft.scope_id), record.record_id):
        raise ValueError("Edition belongs to another textbook")


REGISTRATION = EventRegistration(
    EVENT, 1, "product", "textbook", EventPayload, validate, {(RECORD, 1): Edition}
)


async def project(db: AsyncConnection, event: StoredEvent) -> None:
    record = event.payload.records[0]
    if not isinstance(record.content, InlineContent):
        raise ValueError("Projection requires a hydrated edition")
    async with application(db, "product.material_editions", 1, event.draft.event_id) as needed:
        if needed:
            value = Edition.model_validate_json(canonical_json(record.content.value))
            await write_snapshot(db, value, event.draft.event_id)


async def write_snapshot(db: AsyncConnection, value: Edition, event_id: UUID) -> None:
    data = value.model_dump(mode="json", exclude={"nodes", "issues"})
    data["pending"] = {
        "correction": data["pending"],
        "base_edition_id": data.pop("base_edition_id"),
        "issues": value.issues,
        "related": data.pop("related_tasks"),
    }
    await db.execute(
        text("""
        INSERT INTO product.material_edition SELECT * FROM jsonb_populate_record(
            NULL::product.material_edition, CAST(:data AS jsonb))
        ON CONFLICT (edition_id) DO UPDATE SET revision=excluded.revision,status=excluded.status,
            pending=excluded.pending,entries=excluded.entries,source_event_id=excluded.source_event_id
    """),
        {"data": canonical_json({**data, "source_event_id": str(event_id)})},
    )
    if value.kind != "tree":
        return
    await db.execute(
        text("DELETE FROM product.material_content_node WHERE material_version_id=:id"),
        {"id": value.edition_id},
    )
    rows = [
        {"material_version_id": str(value.edition_id), **n.model_dump(mode="json")}
        for n in value.nodes
    ]
    await db.execute(
        text("""
        INSERT INTO product.material_content_node SELECT * FROM jsonb_populate_recordset(
            NULL::product.material_content_node, CAST(:rows AS jsonb))
    """),
        {"rows": canonical_json(rows)},
    )
