"""不可变文件登记及FileReceived的完整正文；不承接教材或AI业务。"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from deermind.foundation.system.events.contracts import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    InlineContent,
    NonEmpty,
    Ref,
    StoredEvent,
)
from deermind.foundation.system.events.store import canonical_json
from deermind.foundation.system.files.ports import FileBytes
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class FileObject(FactModel):
    file_id: UUID
    backend: Literal["local", "pvc", "object"]
    storage_key: NonEmpty
    media_type: NonEmpty
    byte_size: Annotated[int, Field(ge=0)]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    category: Literal[
        "original", "page", "render", "ai_material", "ai_candidate", "sdk_payload", "fact"
    ]
    artifact_key: NonEmpty | None
    source_refs: list[Ref]
    transform_ref: Ref | None
    created_at: datetime

    def bytes_ref(self) -> FileBytes:
        return FileBytes(self.file_id, self.storage_key, self.byte_size, self.sha256)


class FileReceived(EventPayload):
    subject_ref: Ref
    outcome: Literal["recorded"]
    reason_code: None


def file_content(payload: EventPayload) -> FileObject:
    if not isinstance(payload, FileReceived) or len(payload.records) != 1:
        raise ValueError("FileReceived requires one file record")
    record = payload.records[0]
    if (
        record.record_type != "runtime.file_objects"
        or record.schema_version != 1
        or not isinstance(record.content, InlineContent)
    ):
        raise ValueError("Invalid file registration record")
    return FileObject.model_validate_json(canonical_json(record.content.value))


def validate_file(draft: EventDraft, payload: EventPayload) -> None:
    file = file_content(payload)
    owner = Ref(owner="runtime", type="file", id=str(file.file_id))
    if (
        not isinstance(payload, FileReceived)
        or payload.subject_ref != owner
        or draft.owner_ref != owner
        or draft.scope_id != file.file_id
    ):
        raise ValueError("File registration identity mismatch")


async def project_file(connection: AsyncConnection, event: StoredEvent) -> None:
    file = file_content(event.payload)
    parameters = file.model_dump()
    parameters["source_refs"] = canonical_json(
        [ref.model_dump(exclude_none=True) for ref in file.source_refs]
    )
    parameters["transform_ref"] = (
        file.transform_ref.model_dump_json(exclude_none=True) if file.transform_ref else None
    )
    await connection.execute(
        text(
            "INSERT INTO runtime.file_objects "
            "(file_id, backend, storage_key, media_type, byte_size, sha256, category, "
            "artifact_key, source_refs, transform_ref, created_at) VALUES "
            "(:file_id, :backend, :storage_key, :media_type, :byte_size, :sha256, :category, "
            ":artifact_key, CAST(:source_refs AS jsonb), CAST(:transform_ref AS jsonb), "
            ":created_at)"
        ),
        parameters,
    )


FILE_REGISTRATION = EventRegistration(
    event_type="FileReceived",
    schema_version=1,
    producer="runtime",
    scope_kind="file",
    payload_model=FileReceived,
    validate=validate_file,
    projector_id="runtime.file_objects.v1",
    project=project_file,
)
