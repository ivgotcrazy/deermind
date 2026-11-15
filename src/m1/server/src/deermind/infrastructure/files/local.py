"""本地磁盘和PVC的字节适配；发布后只读，不接受调用方提供的路径。"""

import hashlib
import os
import stat
from pathlib import Path
from typing import BinaryIO, Literal
from uuid import uuid4

from deermind.foundation.system.files.ports import FileBytes


class LocalFiles:
    """固定到已存在的根目录；PVC模式必须是真实挂载，不能回落到容器目录。"""

    def __init__(self, root: Path, *, backend: Literal["local", "pvc"]) -> None:
        if not root.is_absolute() or root.resolve() != root or not root.is_dir():
            raise ValueError("File root must be an existing absolute path without symlinks")
        if backend == "pvc" and not root.is_mount():
            raise OSError("Configured PVC is not mounted")
        self.root = root
        self.backend: Literal["local", "pvc"] = backend
        root_stat = root.stat()
        self._identity = (root_stat.st_dev, root_stat.st_ino)

    def _open_root(self) -> int:
        """每次打开目录核对身份，避免挂载丢失后写到同名的空目录。"""
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        current = os.fstat(descriptor)
        if (current.st_dev, current.st_ino) != self._identity:
            os.close(descriptor)
            raise OSError("Storage root has changed")
        return descriptor

    def save(self, source: BinaryIO, *, max_bytes: int) -> FileBytes:
        """有限流式写入并fsync；硬链接发布禁止覆盖，失败不返回可用文件身份。"""
        if max_bytes < 1:
            raise ValueError("A positive file size limit is required")
        file_id = uuid4()
        storage_key = f"{file_id.hex}.blob"
        temporary = f".writing-{file_id.hex}"
        directory = self._open_root()
        created = False
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            created = True
            digest = hashlib.sha256()
            size = 0
            with os.fdopen(descriptor, "wb") as output:
                while chunk := source.read(min(1024 * 1024, max_bytes - size + 1)):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("File exceeds its size limit")
                    output.write(chunk)
                    digest.update(chunk)
                output.flush()
                os.fchmod(output.fileno(), 0o440)
                os.fsync(output.fileno())
            os.link(
                temporary,
                storage_key,
                src_dir_fd=directory,
                dst_dir_fd=directory,
                follow_symlinks=False,
            )
            os.fsync(directory)
            return FileBytes(file_id, storage_key, size, digest.hexdigest())
        finally:
            # 只清理由本次调用创建的临时名；正式文件即使未登记也不自动删除。
            try:
                if created:
                    os.unlink(temporary, dir_fd=directory)
                    os.fsync(directory)
            finally:
                os.close(directory)

    def read(self, file: FileBytes, *, max_bytes: int) -> bytes:
        """按登记长度/hash检查后才返回内容；缺失或损坏不以空内容代替。"""
        if file.storage_key != f"{file.file_id.hex}.blob":
            raise ValueError("File key does not match its identity")
        if file.byte_size < 0 or file.byte_size > max_bytes:
            raise ValueError("File exceeds the read limit")
        directory = self._open_root()
        try:
            descriptor = os.open(
                file.storage_key,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=directory,
            )
            with os.fdopen(descriptor, "rb") as source:
                metadata = os.fstat(source.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != file.byte_size:
                    raise OSError("Stored file size or type is invalid")
                content = source.read(file.byte_size + 1)
                if (
                    len(content) != file.byte_size
                    or hashlib.sha256(content).hexdigest() != file.sha256
                ):
                    raise OSError("Stored file integrity check failed")
                return content
        finally:
            os.close(directory)
