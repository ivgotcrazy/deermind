"""在现有文件区持久化运行载荷，按固定身份读取。"""

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
        if not content or hashlib.sha256(content).hexdigest() != sha256:
            raise ValueError("Invalid SDK payload bytes or hash")
        key = f"sdk-payload:v1:{sha256}"
        existing = await self.registry.by_artifact(key)
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
            if await self._read(file, len(content), sha256) != content:
                raise OSError("SDK payload failed file readback")
            try:
                await self.registry.register(file, ACTOR)
            except IntegrityError:
                existing = await self.registry.by_artifact(key)
                if existing is None:
                    raise
            else:
                return file.file_id
        if await self._read(existing, len(content), sha256) != content:
            raise OSError("SDK payload does not match its existing registration")
        return existing.file_id

    async def read_payload(self, file_id: UUID, *, byte_size: int, sha256: str) -> bytes:
        """限制到本部署已登记且匹配引用的运行载荷。"""
        file = await self.registry.by_id(file_id)
        if file is None:
            raise FileNotFoundError("SDK payload registration is missing")
        return await self._read(file, byte_size, sha256)

    async def _read(self, file: FileObject, byte_size: int, sha256: str) -> bytes:
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
