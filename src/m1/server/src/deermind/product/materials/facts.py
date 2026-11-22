"""教材收件事实及 Product 自己的投影器。"""

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
from deermind.foundation.system.public.errors import Issue
from deermind.product.public.materials import Revision, TextbookRow
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

RECEIVED = "MaterialReceived"
TEXTBOOK = "product.textbook"
IMPORT = "product.material_import"
SOURCE = "product.material_source"


class MaterialImportFact(FactModel):
    import_id: UUID
    textbook_id: UUID
    status: Literal["active", "deleted"]
    revision: Revision
    source_revision: Revision
    content_revision: int
    created_at: datetime
    updated_at: datetime


class SourcePage(FactModel):
    page_id: UUID
    file_page_index: Revision
    printed_page_label: str | None
    derived_file_ref: Ref | None


class MaterialSourceFact(FactModel):
    source_id: UUID
    import_id: UUID
    file_id: UUID
    original_name: str
    source_order: Revision
    pages: list[SourcePage]
    sha256: str
    created_at: datetime

    def ref(self) -> Ref:
        return Ref(owner="product", type="material_source", id=str(self.source_id))


class MaterialReceived(EventPayload):
    import_id: UUID
    textbook_id: UUID
    source_refs: list[Ref]
    source_revision: Revision
    failed: list[Issue]


def record(kind: str, identity: UUID, value: FactModel) -> FactRecord:
    return FactRecord(
        record_id=str(identity),
        record_type=kind,
        schema_version=1,
        content=InlineContent(storage="inline", value=value.model_dump(mode="json")),
    )


def validate(draft: EventDraft, payload: EventPayload) -> None:
    if not isinstance(payload, MaterialReceived) or draft.scope_id != payload.import_id:
        raise ValueError("MaterialReceived belongs to its import")
    imports: list[MaterialImportFact] = []
    textbooks: list[TextbookRow] = []
    sources: list[MaterialSourceFact] = []
    for row in payload.records:
        if not isinstance(row.content, InlineContent):
            raise ValueError("Validation requires complete material records")
        raw = canonical_json(row.content.value)
        if row.record_type == IMPORT:
            imports.append(MaterialImportFact.model_validate_json(raw))
        elif row.record_type == TEXTBOOK:
            textbooks.append(TextbookRow.model_validate_json(raw))
        elif row.record_type == SOURCE:
            sources.append(MaterialSourceFact.model_validate_json(raw))
        else:
            raise ValueError("Unexpected material record")
    if len(imports) != 1 or not sources:
        raise ValueError("MaterialReceived requires one import and at least one source")
    imported = imports[0]
    if (
        draft.owner_ref != Ref(owner="product", type="material_import", id=str(payload.import_id))
        or imported.status != "active"
        or imported.import_id != payload.import_id
        or imported.textbook_id != payload.textbook_id
        or imported.source_revision != payload.source_revision
        or len(textbooks) != (1 if imported.source_revision == 1 else 0)
        or any(
            book.import_id != imported.import_id or book.textbook_id != imported.textbook_id
            for book in textbooks
        )
        or any(source.import_id != imported.import_id for source in sources)
        or [source.ref() for source in sources] != payload.source_refs
    ):
        raise ValueError("MaterialReceived records do not match their references")


REGISTRATION = EventRegistration(
    event_type=RECEIVED,
    schema_version=1,
    producer="product",
    scope_kind="material_import",
    payload_model=MaterialReceived,
    record_models={
        (TEXTBOOK, 1): TextbookRow,
        (IMPORT, 1): MaterialImportFact,
        (SOURCE, 1): MaterialSourceFact,
    },
    validate=validate,
)

_IMPORT_COLUMNS = (
    "import_id,textbook_id,status,revision,source_revision,content_revision,"
    "created_at,updated_at,source_event_id"
)


async def project(connection: AsyncConnection, event: StoredEvent) -> None:
    """首次写入导入及教材，之后只推进原件修订和追加来源。"""
    for record_ in event.payload.records:
        if not isinstance(record_.content, InlineContent):
            raise ValueError("Projection requires hydrated records")
        table = record_.record_type
        if table == IMPORT:
            statement = (
                f"INSERT INTO product.material_import ({_IMPORT_COLUMNS}) "
                f"SELECT {_IMPORT_COLUMNS} FROM jsonb_populate_record("
                "NULL::product.material_import,CAST(:value AS jsonb)) "
                "ON CONFLICT (import_id) DO UPDATE SET revision=excluded.revision,"
                "source_revision=excluded.source_revision,updated_at=excluded.updated_at,"
                "source_event_id=excluded.source_event_id"
            )
        elif table == TEXTBOOK:
            statement = (
                "INSERT INTO product.textbook SELECT * FROM "
                "jsonb_populate_record(NULL::product.textbook,CAST(:value AS jsonb))"
            )
        elif table == SOURCE:
            statement = (
                "INSERT INTO product.material_source SELECT * FROM "
                "jsonb_populate_record(NULL::product.material_source,CAST(:value AS jsonb))"
            )
        else:
            raise ValueError("Unknown material projection")
        await connection.execute(
            text(statement),
            {
                "value": canonical_json(
                    {**record_.content.value, "source_event_id": str(event.draft.event_id)}
                )
            },
        )
