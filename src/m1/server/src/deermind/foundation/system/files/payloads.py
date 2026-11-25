"""在现有文件区持久化运行载荷，按固定身份读取。

分层定位：foundation（公共运行底座 / 运行载荷存储）
对外契约：RuntimePayloadFiles 保存 SDK 运行载荷并按已登记身份与摘要读取。
边界约束：载荷为 protobuf 编码；相同产物按 artifact_key 复用，读取前核验后端、类别、格式与摘要。
"""

import asyncio
import hashlib
import io
from datetime import UTC, datetime
from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.abstractions.file_records import FileObject
from deermind.abstractions.files import FileStorage
from deermind.foundation.system.files.registry import FileRegistry
from sqlalchemy.exc import IntegrityError

# 载荷媒体类型、编码格式身份与登记执行者身份。
MEDIA_TYPE = "application/x-protobuf"
FORMAT = Ref(owner="runtime", type="encoding", id="temporal-payload-protobuf", version=1)
ACTOR = Ref(owner="runtime", type="service", id="temporal-payload-codec")


class RuntimePayloadFiles:
    """先保存并回读校验，再登记文件。已登记的相同产物可复用。"""

    def __init__(self, registry: FileRegistry, files: FileStorage) -> None:
        self.registry = registry
        self.files = files

    async def save_payload(self, content: bytes, sha256: str) -> UUID:
        """返回已就绪的文件 UUID。并发写入使用同一已提交登记。"""
        # 空载荷或重算摘要与给定摘要不符，拒绝落存。
        if not content or hashlib.sha256(content).hexdigest() != sha256:
            raise ValueError("Invalid SDK payload bytes or hash")
        key = f"sdk-payload:v1:{sha256}"
        existing = await self.registry.by_artifact(key)
        # 无既有登记：保存字节并构造载荷文件记录。
        if existing is None:
            saved = await asyncio.to_thread(
                self.files.save, io.BytesIO(content), max_bytes=len(content)
            )
            file = FileObject(
                file_id=saved.file_id,
                backend=self.files.backend,
                storage_key=saved.storage_key,
                media_type=MEDIA_TYPE,
                byte_size=saved.byte_size,
                sha256=saved.sha256,
                category="sdk_payload",
                artifact_key=key,
                source_refs=[],
                transform_ref=FORMAT,
                created_at=datetime.now(UTC),
            )
            # 回读字节与原载荷不符，判存储不一致，放弃登记。
            if await self._read(file, len(content), sha256) != content:
                raise OSError("SDK payload failed file readback")
            try:
                await self.registry.register(file, ACTOR)
            except IntegrityError:
                # 并发写入冲突：以已提交登记为准，重新取回既有记录。
                existing = await self.registry.by_artifact(key)
                if existing is None:
                    raise
            else:
                return file.file_id
        # 既有产物复用前同样回读核验字节与摘要一致。
        if await self._read(existing, len(content), sha256) != content:
            raise OSError("SDK payload does not match its existing registration")
        return existing.file_id

    async def read_payload(self, file_id: UUID, *, byte_size: int, sha256: str) -> bytes:
        """限制到本部署已登记且匹配引用的运行载荷。"""
        file = await self.registry.by_id(file_id)
        # 登记记录缺失，不能凭 file_id 直接读后端载荷。
        if file is None:
            raise FileNotFoundError("SDK payload registration is missing")
        return await self._read(file, byte_size, sha256)

    async def _read(self, file: FileObject, byte_size: int, sha256: str) -> bytes:
        """核验登记身份、类别、格式、大小与摘要一致后读取载荷字节。"""
        # 后端、类别、媒体类型、工件键、编码格式、大小与摘要任一不符，判引用与登记不一致。
        if (
            file.backend != self.files.backend
            or file.category != "sdk_payload"
            or file.media_type != MEDIA_TYPE
            or file.artifact_key != f"sdk-payload:v1:{sha256}"
            or file.transform_ref != FORMAT
            or file.byte_size != byte_size
            or file.sha256 != sha256
        ):
            raise ValueError("SDK payload reference does not match its registration")
        return await asyncio.to_thread(self.files.read, file.bytes_ref(), max_bytes=byte_size)
