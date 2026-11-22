"""文件字节端口；路径规则和挂载检查由后端实现，不包含业务授权。"""

from dataclasses import dataclass
from typing import BinaryIO, Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class FileBytes:
    file_id: UUID
    storage_key: str
    byte_size: int
    sha256: str


class FileStorage(Protocol):
    @property
    def backend(self) -> Literal["local", "pvc", "object"]: ...

    def save(self, source: BinaryIO, *, max_bytes: int) -> FileBytes: ...

    def read(self, file: FileBytes, *, max_bytes: int) -> bytes: ...


class PayloadStorage(Protocol):
    """保存及读取本部署已登记的运行载荷。"""

    async def save_payload(self, content: bytes, sha256: str) -> UUID: ...

    async def read_payload(self, file_id: UUID, *, byte_size: int, sha256: str) -> bytes: ...
