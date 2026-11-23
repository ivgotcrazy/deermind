"""Keep the evaluation cursor in original learning-space event order."""

from uuid import UUID

from deermind.abstractions.event_reading import EventFilter
from deermind.abstractions.events import FactModel
from deermind.foundation.system.events.query import EventReader
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class SourceEvent(FactModel):
    event_id: UUID
    event_type: str
    scope_event_seq: int


async def next_source(
    db: AsyncConnection, reader: EventReader, scope: UUID, types: tuple[str, ...]
) -> SourceEvent | None:
    args = {"scope": scope}
    await db.execute(
        text("""
        INSERT INTO evaluation.evaluation_progress (scope_id) VALUES (:scope)
        ON CONFLICT DO NOTHING
    """),
        args,
    )
    row = (
        await db.execute(
            text("""
        SELECT scanned_through_seq, active_trigger_event_id
        FROM evaluation.evaluation_progress WHERE scope_id=:scope FOR UPDATE
    """),
            args,
        )
    ).one()
    if row.active_trigger_event_id is not None:
        return None
    page = await reader.query_metadata(
        "learning_space",
        scope,
        filters=EventFilter(event_types=types),
        after_seq=row.scanned_through_seq,
        limit=1,
        connection=db,
    )
    items = page["items"]
    if not isinstance(items, list) or not items:
        return None
    item = items[0]
    if not isinstance(item, dict):
        raise ValueError("Evaluation source metadata is invalid")
    return SourceEvent(
        event_id=UUID(str(item["event_id"])),
        event_type=str(item["event_type"]),
        scope_event_seq=int(str(item["scope_event_seq"])),
    )


async def begin(db: AsyncConnection, scope: UUID, event: SourceEvent) -> None:
    await db.execute(
        text("""
        UPDATE evaluation.evaluation_progress
        SET active_trigger_event_id=:trigger, active_source_seq=:seq WHERE scope_id=:scope
    """),
        {"scope": scope, "trigger": event.event_id, "seq": event.scope_event_seq},
    )


async def protect(db: AsyncConnection, scope: UUID, trigger: UUID) -> None:
    active = await db.scalar(
        text("""
        SELECT active_trigger_event_id FROM evaluation.evaluation_progress
        WHERE scope_id=:scope FOR UPDATE
    """),
        {"scope": scope},
    )
    if active != trigger:
        raise ValueError("This evaluation is not the active source for its space")


async def finish(db: AsyncConnection, scope: UUID) -> None:
    await db.execute(
        text("""
        UPDATE evaluation.evaluation_progress SET scanned_through_seq=active_source_seq,
            active_trigger_event_id=NULL, active_source_seq=NULL WHERE scope_id=:scope
    """),
        {"scope": scope},
    )
