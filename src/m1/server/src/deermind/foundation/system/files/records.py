"""不可变文件登记及 FileReceived 的完整正文；不承接教材或 AI 业务。

分层定位：foundation（公共运行底座 / 文件登记投影）
对外契约：validate_file 校验登记身份；project_file 把 FileReceived 投影到 file_objects 表。
边界约束：只维护运行期不可变文件登记，不承载教材、题目或 AI 产物的业务语义。
"""

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
    """从 FileReceived 正文中取出唯一文件记录并解析为 FileObject。"""
    # FileReceived 正文必须携带恰好一条文件记录。
    if not isinstance(payload, FileReceived) or len(payload.records) != 1:
        raise ValueError("FileReceived requires one file record")
    record = payload.records[0]
    # 记录类型、版本与内联正文不符，判无效文件登记。
    if (
        record.record_type != "runtime.file_objects"
        or record.schema_version != 1
        or not isinstance(record.content, InlineContent)
    ):
        raise ValueError("Invalid file registration record")
    return FileObject.model_validate_json(canonical_json(record.content.value))


def validate_file(draft: EventDraft, payload: EventPayload) -> None:
    """校验文件登记的主体、归属与范围身份一致。"""
    file = file_content(payload)
    owner = Ref(owner="runtime", type="file", id=str(file.file_id))
    # 正文主体、事件所有者与范围编号必须与文件身份一致。
    if (
        not isinstance(payload, FileReceived)
        or payload.subject_ref != owner
        or draft.owner_ref != owner
        or draft.scope_id != file.file_id
    ):
        raise ValueError("File registration identity mismatch")


async def project_file(connection: AsyncConnection, event: StoredEvent) -> None:
    """把已核验的文件对象投影写入文件登记表。"""
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


# FileReceived 事件的类型、版本、生产者与正文 Schema 登记。
FILE_REGISTRATION = EventRegistration(
    event_type="FileReceived",
    schema_version=1,
    producer="runtime",
    scope_kind="file",
    payload_model=FileReceived,
    validate=validate_file,
    record_models={("runtime.file_objects", 1): FileObject},
)
