"""学习目标的不可变快照、保存事实及 Product 投影。"""

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
from deermind.product.public.learning_targets import GoalItem, TargetRef, TargetView
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

EVENT = "LearningTargetSaved"
HEAD = "product.learning_target"
VERSION = "product.learning_target_version"


class TargetHead(FactModel):
    target_id: UUID
    textbook_id: UUID
    head_revision: int
    created_at: datetime


class TargetVersion(FactModel):
    target_id: UUID
    revision: int
    title: str
    items: list[GoalItem]
    chapter_basis: list[Ref]
    gaps: list[Issue]
    actor_ref: Ref
    created_at: datetime

    def as_view(self, textbook_id: UUID) -> TargetView:
        return TargetView(
            target_ref=TargetRef(target_id=self.target_id, revision=self.revision),
            textbook_id=textbook_id,
            title=self.title,
            items=self.items,
            chapter_basis_refs=self.chapter_basis,
            gaps=self.gaps,
        )


class LearningTargetSaved(EventPayload):
    target_ref: TargetRef
    previous_target_ref: TargetRef | None
    textbook_id: UUID
    request_ref: UUID


def validate(draft: EventDraft, payload: EventPayload) -> None:
    if (
        not isinstance(payload, LearningTargetSaved)
        or draft.scope_id != payload.target_ref.target_id
    ):
        raise ValueError("Target fact scope does not match")
    records = {record.record_type: record for record in payload.records}
    if set(records) != {HEAD, VERSION} or len(payload.records) != 2:
        # 变更须同时带头记录和版本记录。
        raise ValueError("Target change requires a head and a version")
    head, version = records[HEAD].content, records[VERSION].content
    assert isinstance(head, InlineContent) and isinstance(version, InlineContent)
    ref = payload.target_ref
    if (
        head.value["target_id"] != str(ref.target_id)
        or version.value["target_id"] != str(ref.target_id)
        or head.value["head_revision"] != ref.revision
        or version.value["revision"] != ref.revision
        or head.value["textbook_id"] != str(payload.textbook_id)
    ):
        # 头/版本快照的目标、修订号与教材归属须与固定引用一致。
        raise ValueError("Target snapshot differs from its fixed reference")


REGISTRATION = EventRegistration(
    EVENT,
    1,
    "product",
    "learning_target",
    LearningTargetSaved,
    validate,
    {(HEAD, 1): TargetHead, (VERSION, 1): TargetVersion},
)

_PROJECTIONS = {
    HEAD: "INSERT INTO product.learning_target SELECT * FROM "
    "jsonb_populate_record(NULL::product.learning_target,CAST(:body AS jsonb)) "
    "ON CONFLICT(target_id) DO UPDATE SET head_revision=EXCLUDED.head_revision,"
    "source_event_id=EXCLUDED.source_event_id",
    VERSION: "INSERT INTO product.learning_target_version SELECT * FROM "
    "jsonb_populate_record(NULL::product.learning_target_version,CAST(:body AS jsonb))",
}


async def project(connection: AsyncConnection, saved: StoredEvent) -> None:
    records = {record.record_type: record.content for record in saved.payload.records}
    async with application(
        connection, "product.learning_targets", 1, saved.draft.event_id
    ) as needed:
        if not needed:
            # 已被回执投影处理过，跳过落表。
            return
        for key, statement in _PROJECTIONS.items():
            record = records[key]
            assert isinstance(record, InlineContent)
            await connection.execute(
                text(statement),
                {
                    "body": canonical_json(
                        {
                            **record.value,
                            "source_event_id": str(saved.draft.event_id),
                        }
                    )
                },
            )
