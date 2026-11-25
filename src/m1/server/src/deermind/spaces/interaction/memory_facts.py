"""活动记忆引用正式原文并通过不可变修订保存。"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid5

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
from deermind.spaces.interaction.conversation_facts import record, ref
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

SAVED = "InteractionMemorySaved"
REVISION = "interaction.memory_revisions"
HISTORY_WINDOW = 12
Kind = Literal["entries", "summary"]


class Remember(FactModel):
    type: Literal["pending_question", "discussion_point", "explicit_preference"]
    quote: str
    resolves: str | None = None


class Entry(FactModel):
    entry_id: str
    type: Literal["pending_question", "discussion_point", "explicit_preference"]
    text: str
    state: Literal["open", "resolved"]
    source_refs: list[Ref]
    resolution_refs: list[Ref]


class MemoryRevision(FactModel):
    memory_id: UUID
    revision: int
    scope_id: UUID
    activity_id: UUID
    kind: Kind
    basis_message_seq: int
    content: dict[str, JsonValue]
    source_ref: Ref
    previous_ref: Ref | None
    created_at: datetime

    @property
    def identity(self) -> Ref:
        return ref("activity_memory", self.memory_id, self.revision)


class MemorySaved(EventPayload):
    memory_ref: Ref
    activity_ref: Ref
    kind: Kind
    source_refs: list[Ref]


def validate(draft: EventDraft, body: EventPayload) -> None:
    # 记忆修订事件须单条记录且带来源引用。
    if not isinstance(body, MemorySaved) or len(body.records) != 1 or not body.source_refs:
        raise ValueError("A memory revision requires exact source references")
    item = body.records[0]
    if item.record_type != REVISION or not isinstance(item.content, InlineContent):
        raise ValueError("Missing memory revision record")
    entry = MemoryRevision.model_validate_json(canonical_json(item.content.value))
    # 范围、记忆引用、所有者、活动、类型与记录编号须逐项一致。
    if (
        entry.scope_id != draft.scope_id
        or entry.identity != body.memory_ref
        or entry.identity != draft.owner_ref
        or str(entry.activity_id) != body.activity_ref.id
        or entry.kind != body.kind
        or item.record_id != f"{entry.memory_id}:{entry.revision}"
    ):
        raise ValueError("Invalid memory revision")


REGISTRATION = EventRegistration(
    SAVED,
    1,
    "interaction",
    "learning_space",
    MemorySaved,
    validate,
    {(REVISION, 1): MemoryRevision},
)


async def read(db: AsyncConnection, scope: UUID, activity: UUID) -> list[MemoryRevision]:
    found = await db.scalars(
        text(
            "SELECT to_jsonb(r)-'source_event_id' FROM interaction.memory_heads h "
            "JOIN interaction.memory_revisions r USING(memory_id,revision) "
            "WHERE h.scope_id=:scope AND h.activity_id=:activity "
            "AND r.scope_id=h.scope_id AND r.activity_id=h.activity_id AND r.kind=h.kind"
        ),
        {"scope": scope, "activity": activity},
    )
    return [MemoryRevision.model_validate_json(canonical_json(row)) for row in found]


def revise(
    scope: UUID,
    activity: Ref,
    source: Ref,
    kind: Kind,
    basis: int,
    content: dict[str, JsonValue],
    evidence: list[Ref],
    previous: MemoryRevision | None,
) -> MemorySaved:
    activity_id = UUID(activity.id)
    saved = MemoryRevision(
        memory_id=uuid5(activity_id, "interaction-memory:" + kind),
        revision=previous.revision + 1 if previous else 1,
        scope_id=scope,
        activity_id=activity_id,
        kind=kind,
        basis_message_seq=basis,
        content=content,
        source_ref=source,
        previous_ref=previous.identity if previous else None,
        created_at=datetime.now(UTC),
    )
    return MemorySaved(
        memory_ref=saved.identity,
        activity_ref=activity,
        kind=kind,
        source_refs=evidence,
        records=[record(REVISION, f"{saved.memory_id}:{saved.revision}", saved)],
    )


def remember(
    proposal: Remember,
    student_text: str,
    reply: str,
    source: Ref,
    response: Ref,
    previous: MemoryRevision | None,
) -> list[Entry] | None:
    wording = proposal.quote.strip()
    # 记忆措辞长度不在区间内，不收录。
    if not 1 <= len(wording) <= 240:
        return None
    raw = previous.content.get("entries") if previous else None
    entries = [Entry.model_validate(row) for row in raw] if isinstance(raw, list) else []
    if proposal.resolves is not None:
        # 闭环提议：找到对应未决条目且答复含该引文时，标记为已解决。
        for index, row in enumerate(entries):
            if row.entry_id == proposal.resolves and row.state == "open" and wording in reply:
                entries[index] = row.model_copy(
                    update={"state": "resolved", "resolution_refs": [response]}
                )
                return entries
        return None
    # 原话中检索不到引文，或条目已重复，不新增。
    if wording not in student_text or any(row.text == wording for row in entries):
        return None
    # 条目数达上限，不再追加。
    if len(entries) >= 24:
        return None
    return [
        *entries,
        Entry(
            entry_id=str(uuid5(UUID(source.id), "working-memory-entry")),
            type=proposal.type,
            text=wording,
            state="open",
            source_refs=[source],
            resolution_refs=[],
        ),
    ]


async def project(db: AsyncConnection, event: StoredEvent) -> None:
    async with application(db, "interaction.memory", 1, event.draft.event_id) as apply:
        # 事件已投影过，重复应用直接返回。
        if not apply:
            return
        item = event.payload.records[0]
        if not isinstance(item.content, InlineContent):
            raise ValueError("Missing decoded memory revision")
        source = {**item.content.value, "source_event_id": str(event.draft.event_id)}
        await db.execute(
            text(
                "INSERT INTO interaction.memory_revisions SELECT * FROM jsonb_populate_record("
                "NULL::interaction.memory_revisions,CAST(:body AS jsonb))"
            ),
            {"body": canonical_json(source)},
        )
        changed = await db.scalar(
            text(
                "INSERT INTO interaction.memory_heads AS head(scope_id,activity_id,kind,"
                "memory_id,revision) SELECT scope_id,activity_id,kind,memory_id,revision "
                "FROM jsonb_populate_record("
                "NULL::interaction.memory_revisions,CAST(:body AS jsonb)) "
                "ON CONFLICT(scope_id,activity_id,kind) DO UPDATE SET revision=EXCLUDED.revision "
                "WHERE head.memory_id=EXCLUDED.memory_id AND head.revision+1=EXCLUDED.revision "
                "RETURNING 1"
            ),
            {"body": canonical_json(source)},
        )
        # 头指针未按 revision+1 推进，说明投影顺序已乱，拒绝落表。
        if changed is None:
            raise ValueError("Memory head advanced before projection")
