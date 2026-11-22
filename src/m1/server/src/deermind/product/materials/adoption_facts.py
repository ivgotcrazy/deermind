"""采用决定的完整事实和教材投影。"""

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
from deermind.product.materials.assistant_facts import BATCH, CandidateBatchFact
from deermind.product.materials.facts import IMPORT, MaterialImportFact
from deermind.product.public.material_assistant import PreviousMaterialBatch
from deermind.product.public.materials import Revision
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

ADOPTED = "MaterialCandidatesAdopted"
DECLINED = "MaterialCandidateDeclined"
DECISION = "product.material_adoption"
CHAPTER = "product.material_chapter"


class MaterialDecision(FactModel):
    decision_id: UUID
    batch_id: UUID
    batch_revision: Revision
    decision: Literal["adopt", "decline"]
    actor_ref: Ref
    before_refs: list[Ref]
    after_refs: list[Ref]
    impact: dict[str, JsonValue]
    request_ref: UUID
    created_at: datetime


class MaterialChapter(FactModel):
    chapter_id: UUID
    textbook_id: UUID
    parent_id: UUID | None
    title: str
    sort_order: int
    page_refs: list[Ref]
    revision: Revision
    catalog_basis_ref: Ref
    updated_at: datetime


class MaterialAdopted(EventPayload):
    import_id: UUID
    adoption_ref: Ref
    adopted_refs: list[Ref]
    replaced_refs: list[Ref]
    affected_submission_refs: list[Ref]


class MaterialDeclined(EventPayload):
    import_id: UUID
    batch_ref: PreviousMaterialBatch
    decision_ref: Ref
    request_ref: UUID


def validate(draft: EventDraft, payload: EventPayload) -> None:
    if (
        not isinstance(payload, (MaterialAdopted, MaterialDeclined))
        or draft.scope_id != payload.import_id
    ):
        raise ValueError("Invalid material decision scope")
    types = [record.record_type for record in payload.records]
    if (
        types.count(DECISION) != 1
        or types.count(BATCH) != 1
        or types.count(IMPORT) != 1
        or (isinstance(payload, MaterialDeclined) and CHAPTER in types)
    ):
        raise ValueError("Invalid material decision records")


REGISTRATIONS = [
    EventRegistration(
        kind,
        1,
        "product",
        "material_import",
        schema,
        validate,
        {
            (DECISION, 1): MaterialDecision,
            (BATCH, 1): CandidateBatchFact,
            (IMPORT, 1): MaterialImportFact,
            (CHAPTER, 1): MaterialChapter,
        },
    )
    for kind, schema in ((ADOPTED, MaterialAdopted), (DECLINED, MaterialDeclined))
]

_STATEMENTS = {
    DECISION: (
        "INSERT INTO product.material_adoption SELECT * FROM "
        "jsonb_populate_record(NULL::product.material_adoption,CAST(:value AS jsonb))"
    ),
    BATCH: (
        "UPDATE product.material_candidate_batch b SET decision_state=v.decision_state,"
        "decision_revision=v.decision_revision,source_event_id=v.source_event_id FROM "
        "jsonb_populate_record(NULL::product.material_candidate_batch,CAST(:value AS jsonb)) v "
        "WHERE v.batch_id=b.batch_id"
    ),
    IMPORT: (
        "UPDATE product.material_import i "
        "SET revision=v.revision,content_revision=v.content_revision,"
        "updated_at=v.updated_at,source_event_id=v.source_event_id FROM "
        "jsonb_populate_record(NULL::product.material_import,CAST(:value AS jsonb)) v "
        "WHERE v.import_id=i.import_id"
    ),
    CHAPTER: (
        "INSERT INTO product.material_chapter SELECT * FROM "
        "jsonb_populate_record(NULL::product.material_chapter,CAST(:value AS jsonb)) "
        "ON CONFLICT(chapter_id) DO UPDATE SET title=excluded.title,sort_order=excluded.sort_order,"
        "page_refs=excluded.page_refs,revision=excluded.revision,"
        "catalog_basis_ref=excluded.catalog_basis_ref,updated_at=excluded.updated_at,"
        "source_event_id=excluded.source_event_id"
    ),
}


async def project(connection: AsyncConnection, event: StoredEvent) -> None:
    """投影精确采用决定后，再由相同事实维护当前内容索引。"""
    result: MaterialDecision | None = None
    for record in event.payload.records:
        if not isinstance(record.content, InlineContent):
            raise ValueError("Projection requires hydrated material decisions")
        if record.record_type == DECISION:
            result = MaterialDecision.model_validate_json(canonical_json(record.content.value))
        await connection.execute(
            text(_STATEMENTS[record.record_type]),
            {
                "value": canonical_json(
                    {**record.content.value, "source_event_id": str(event.draft.event_id)}
                )
            },
        )
    if result is None or result.decision == "decline":
        return
    for old in result.before_refs:
        await connection.execute(
            text(
                "UPDATE product.material_content_current "
                "SET validity='retired',adoption_ref=:decision "
                "WHERE import_id=:import AND candidate_id=:id AND candidate_revision=:revision"
            ),
            {
                "import": event.draft.scope_id,
                "decision": result.decision_id,
                "id": UUID(old.id),
                "revision": old.revision,
            },
        )
    for adopted in result.after_refs:
        await connection.execute(
            text(
                "INSERT INTO product.material_content_current SELECT c.import_id,c.candidate_id,"
                "c.candidate_revision,(c.chapter_ref->>'id')::uuid,'current',:decision "
                "FROM product.material_candidate c WHERE c.candidate_id=:id "
                "AND c.candidate_revision=:revision AND c.import_id=:import "
                "ON CONFLICT(import_id,candidate_id) DO UPDATE SET "
                "candidate_revision=excluded.candidate_revision,chapter_id=excluded.chapter_id,"
                "validity='current',adoption_ref=excluded.adoption_ref"
            ),
            {
                "import": event.draft.scope_id,
                "decision": result.decision_id,
                "id": UUID(adopted.id),
                "revision": adopted.revision,
            },
        )
