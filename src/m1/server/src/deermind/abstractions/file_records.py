"""文件登记数据与事件正文；无存储及投影实现。

分层定位：abstractions（跨层合同）
对外契约：FileObject 文件登记记录与 FileReceived 事件正文。
边界约束：只定义文件身份与事件结构，不含字节存储与授权核验。
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from deermind.abstractions.events import EventPayload, FactModel, NonEmpty, Ref
from deermind.abstractions.files import FileBytes


class FileObject(FactModel):
    """已登记文件的身份、后端、存储键、完整性信息与分类来源。"""

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
        """生成字节读取所需的精简引用（不含媒体类型与分类等登记信息）。"""
        return FileBytes(self.file_id, self.storage_key, self.byte_size, self.sha256)


class FileReceived(EventPayload):
    """文件完整保存且校验通过的事件正文。"""

    subject_ref: Ref
    outcome: Literal["recorded"]
    reason_code: None
