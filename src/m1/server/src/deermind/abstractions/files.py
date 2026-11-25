"""文件字节端口；路径规则和挂载检查由后端实现，不包含业务授权。

分层定位：abstractions（跨层合同）
对外契约：FileBytes 字节定位与 FileStorage、PayloadStorage 两个存储端口。
边界约束：只定义字节读写接口，路径/挂载规则与业务授权在基础设施实现。
"""

from dataclasses import dataclass
from typing import BinaryIO, Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class FileBytes:
    """定位一份字节内容的最小引用：编号、存储键、大小与摘要。"""

    file_id: UUID
    storage_key: str
    byte_size: int
    sha256: str


class FileStorage(Protocol):
    """文件字节存储端口：保存与读取，均带大小上限。"""

    @property
    def backend(self) -> Literal["local", "pvc", "object"]: ...

    def save(self, source: BinaryIO, *, max_bytes: int) -> FileBytes: ...

    def read(self, file: FileBytes, *, max_bytes: int) -> bytes: ...


class PayloadStorage(Protocol):
    """保存及读取本部署已登记的运行载荷。"""

    async def save_payload(self, content: bytes, sha256: str) -> UUID: ...

    async def read_payload(self, file_id: UUID, *, byte_size: int, sha256: str) -> bytes: ...
