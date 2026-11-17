"""文件登记数据与事件正文；无存储及投影实现。"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from deermind.abstractions.events import EventPayload, FactModel, NonEmpty, Ref
from deermind.abstractions.files import FileBytes


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
