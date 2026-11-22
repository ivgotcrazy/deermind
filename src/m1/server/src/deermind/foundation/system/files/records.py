"""不可变文件登记及FileReceived的完整正文；不承接教材或AI业务。"""

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    InlineContent,
    Ref,
    StoredEvent,
)
from deermind.abstractions.file_records import FileObject, FileReceived
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


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
    record_models={("runtime.file_objects", 1): FileObject},
)
