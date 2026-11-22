"""登记和接收有限流式上传，文件完整发布后才保存完成状态。"""

import asyncio
import hashlib
import time
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import UTC, datetime
from tempfile import TemporaryFile
from typing import Annotated, Any, BinaryIO, Literal
from uuid import UUID, uuid4

from deermind.abstractions.events import FactModel, Ref
from deermind.abstractions.file_records import FileObject
from deermind.abstractions.files import FileStorage
from deermind.foundation.system.files.registry import FileRegistry
from deermind.foundation.system.public.errors import ErrorDetail, RequestError
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine

type OriginalMedia = Literal["application/pdf", "image/png", "image/jpeg"]
type JsonUUID = Annotated[UUID, Field(strict=False)]
MAX_BYTES: dict[str, int] = {
    "application/pdf": 512 * 1024 * 1024,
    "image/png": 32 * 1024 * 1024,
    "image/jpeg": 32 * 1024 * 1024,
}


class FileReceipt(FactModel):
    storage_ref: JsonUUID
    media_type: OriginalMedia
    byte_size: Annotated[int, Field(gt=0)]
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class UploadView(FactModel):
    upload_id: UUID
    state: Literal["receiving", "ready", "failed"]
    receipt: FileReceipt | None = None
    error: ErrorDetail | None = None


_UPLOAD = text(
    "SELECT u.*, f.byte_size, f.sha256 FROM runtime.file_uploads u "
    "LEFT JOIN runtime.file_objects f USING (file_id) "
    "WHERE u.upload_id=:id AND u.principal_id=:owner"
)


def file_view(row: RowMapping | Mapping[str, Any]) -> FileReceipt:
    return FileReceipt(
        storage_ref=row["file_id"],
        media_type=row["declared_media_type"],
        byte_size=row["byte_size"],
        sha256=row["sha256"],
    )


def upload_view(row: RowMapping) -> UploadView:
    return UploadView(
        upload_id=row["upload_id"],
        state=row["state"],
        receipt=file_view(row) if row["state"] == "ready" else None,
        error=ErrorDetail.model_validate(row["error"]) if row["error"] else None,
    )


class FileUploads:
    """业务入口先核对用途权限，上传只持短事务和有限文件资源。"""

    def __init__(
        self, engine: AsyncEngine, files: FileStorage, inspect: Callable[[BinaryIO, str], int]
    ) -> None:
        self.engine = engine
        self.files = files
        self.registry = FileRegistry(engine)
        self.inspect = inspect
        self.running = asyncio.Semaphore(2)

    async def register(
        self,
        owner: UUID,
        request_id: str,
        name: str,
        media: OriginalMedia,
        size: int,
        domain_ref: str,
        import_id: UUID | None,
    ) -> UploadView:
        if not 0 < size <= MAX_BYTES[media]:
            raise RequestError(413, "payload_too_large", "文件大小超出此格式的上限。")
        resource = (
            Ref(owner="product", type="material_import", id=str(import_id)).model_dump_json(
                exclude_none=True
            )
            if import_id
            else None
        )
        keys = {
            "owner": str(owner),
            "id": uuid4(),
            "request": request_id,
            "name": name,
            "media": media,
            "size": size,
            "domain": domain_ref,
            "resource": resource,
        }
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO runtime.file_uploads VALUES "
                    "(:id,:owner,'material_source',CAST(:resource AS jsonb),"
                    "CAST(:domain AS jsonb),:request,:name,:media,:size,'receiving',:id,"
                    "clock_timestamp(),NULL,NULL,NULL,clock_timestamp(),clock_timestamp()) "
                    "ON CONFLICT (principal_id,purpose,request_id) DO NOTHING"
                ),
                keys,
            )
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT u.*, f.byte_size, f.sha256, "
                            "u.domain_ref=CAST(:domain AS jsonb) AND "
                            "u.resource_ref IS NOT DISTINCT FROM CAST(:resource AS jsonb) "
                            "AS same_scope FROM runtime.file_uploads u "
                            "LEFT JOIN runtime.file_objects f USING(file_id) "
                            "WHERE principal_id=:owner AND purpose='material_source' "
                            "AND request_id=:request"
                        ),
                        keys,
                    )
                )
                .mappings()
                .one()
            )
        if (
            not row["same_scope"]
            or row["original_name"] != name
            or row["declared_media_type"] != media
            or row["declared_size"] != size
        ):
            raise RequestError(409, "request_conflict", "同一上传编号已用于另一份文件或范围。")
        return upload_view(row)

    async def read(self, owner: UUID, upload_id: UUID) -> RowMapping:
        async with self.engine.connect() as connection:
            row = (
                (await connection.execute(_UPLOAD, {"id": upload_id, "owner": str(owner)}))
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise RequestError(404, "not_found", "找不到上传记录。")
        return row

    async def _renew(self, upload_id: UUID, attempt: UUID) -> None:
        async with self.engine.begin() as connection:
            renewed = await connection.scalar(
                text(
                    "UPDATE runtime.file_uploads "
                    "SET lease_until=clock_timestamp()+interval '90 seconds' "
                    "WHERE upload_id=:id AND write_attempt_id=:attempt AND state='receiving' "
                    "AND lease_until>clock_timestamp() RETURNING upload_id"
                ),
                {"id": upload_id, "attempt": attempt},
            )
        if renewed is None:
            raise RequestError(409, "upload_busy", "上传已过期，请重新发送文件。")

    async def write(
        self, owner: UUID, row: RowMapping, media: str, chunks: AsyncIterator[bytes]
    ) -> UploadView:
        """复用原上传身份，核对实际大小及内容，保存已完成收据。"""
        upload_id: UUID = row["upload_id"]
        if media != row["declared_media_type"]:
            raise RequestError(415, "unsupported_media_type", "文件类型与登记不符。")
        if self.running.locked():
            raise RequestError(429, "upload_busy", "正在接收其他文件，请稍后重试。")
        async with self.running:
            return await self._receive(owner, row, upload_id, chunks)

    async def _receive(
        self, owner: UUID, row: RowMapping, upload_id: UUID, chunks: AsyncIterator[bytes]
    ) -> UploadView:
        ready = row["state"] == "ready"
        attempt = uuid4()
        keys = {"id": upload_id, "attempt": attempt}
        if not ready:
            async with self.engine.begin() as connection:
                claimed = await connection.scalar(
                    text(
                        "UPDATE runtime.file_uploads SET state='receiving',error=NULL,"
                        "write_attempt_id=:attempt,"
                        "lease_until=clock_timestamp()+interval '90 seconds',"
                        "updated_at=clock_timestamp() WHERE upload_id=:id AND state<>'ready' "
                        "AND lease_until<=clock_timestamp() RETURNING upload_id"
                    ),
                    keys,
                )
            if claimed is None:
                raise RequestError(409, "upload_busy", "文件正在上传，请先查询上传结果。")

        size: int = row["declared_size"]
        media: OriginalMedia = row["declared_media_type"]
        try:
            async with asyncio.timeout(20 * 60):
                with TemporaryFile(mode="w+b") as source:
                    received = 0
                    renew_at = time.monotonic() + 30
                    digest = hashlib.sha256()
                    while True:
                        try:
                            async with asyncio.timeout(60):
                                chunk = await anext(chunks)
                        except StopAsyncIteration:
                            break
                        received += len(chunk)
                        if received > size:
                            raise RequestError(413, "payload_too_large", "上传超过声明的字节数。")
                        if ready:
                            digest.update(chunk)
                        else:
                            source.write(chunk)
                            if time.monotonic() >= renew_at:
                                await self._renew(upload_id, attempt)
                                renew_at = time.monotonic() + 30
                    if received != size:
                        raise RequestError(
                            422, "source_unavailable", "文件字节不完整，请重新上传。"
                        )
                    if ready:
                        if digest.hexdigest() != row["sha256"]:
                            raise RequestError(
                                409, "content_conflict", "此上传编号已有不同的文件。"
                            )
                        return upload_view(row)

                    pages, file = await self._check_and_save(source, media, size, upload_id)
                    await self._complete(owner, upload_id, attempt, pages, file)
        except (RequestError, TimeoutError, OSError, ValueError) as error:
            if isinstance(error, TimeoutError):
                failure = RequestError(409, "upload_timeout", "上传超时，请重传此文件。")
            elif isinstance(error, OSError):
                failure = RequestError(503, "source_unavailable", "暂时无法保存原件，请重试。")
            elif isinstance(error, ValueError):
                failure = RequestError(415, "unsupported_media_type", "文件损坏或格式不符合要求。")
            else:
                failure = error
            if not ready:
                await self._fail(upload_id, attempt, failure)
            raise failure from error if failure is not error else None
        return upload_view(await self.read(owner, upload_id))

    async def _check_and_save(
        self, source: BinaryIO, media: OriginalMedia, size: int, upload_id: UUID
    ) -> tuple[int, FileObject]:
        def validate() -> tuple[int, FileObject]:
            pages = self.inspect(source, media)
            saved = self.files.save(source, max_bytes=size)
            return pages, FileObject(
                **vars(saved),
                backend=self.files.backend,
                media_type=media,
                category="original",
                artifact_key=None,
                source_refs=[Ref(owner="runtime", type="file_upload", id=str(upload_id))],
                transform_ref=None,
                created_at=datetime.now(UTC),
            )

        # 线程读完后才能关闭暂存文件；取消仍会丢弃本次结果。
        job = asyncio.create_task(asyncio.to_thread(validate))
        try:
            return await asyncio.shield(job)
        except asyncio.CancelledError:
            await asyncio.gather(job, return_exceptions=True)
            raise

    async def _complete(
        self, owner: UUID, upload_id: UUID, attempt: UUID, pages: int, file: FileObject
    ) -> None:
        async with self.engine.begin() as connection:
            keys = {"id": upload_id, "attempt": attempt, "file": file.file_id, "pages": pages}
            current = await connection.scalar(
                text(
                    "SELECT upload_id FROM runtime.file_uploads WHERE upload_id=:id "
                    "AND write_attempt_id=:attempt AND state='receiving' "
                    "AND lease_until>clock_timestamp() FOR UPDATE"
                ),
                keys,
            )
            if current is None:
                raise RequestError(409, "upload_busy", "上传已过期，请重新发送文件。")
            await self.registry.register_in(
                connection,
                file,
                Ref(owner="product", type="account", id=str(owner)),
                source_request_id=str(upload_id),
            )
            await connection.execute(
                text(
                    "UPDATE runtime.file_uploads SET state='ready',page_count=:pages,"
                    "file_id=:file,updated_at=clock_timestamp() WHERE upload_id=:id"
                ),
                keys,
            )

    async def _fail(self, upload_id: UUID, attempt: UUID, error: RequestError) -> None:
        detail = ErrorDetail(
            code=error.code,
            message=error.message,
            issues=error.issues,
            retryable=error.status == 503,
        )
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE runtime.file_uploads SET state='failed',error=CAST(:error AS jsonb),"
                    "lease_until=clock_timestamp(),updated_at=clock_timestamp() "
                    "WHERE upload_id=:id AND write_attempt_id=:attempt AND state='receiving'"
                ),
                {"id": upload_id, "attempt": attempt, "error": detail.model_dump_json()},
            )

    async def completed(self, owner: UUID, file_ids: list[UUID]) -> dict[UUID, RowMapping]:
        """只向同一上传人提供其固定完成记录，业务模块还须核对导入范围。"""
        async with self.engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT u.*, f.byte_size, f.sha256 FROM runtime.file_uploads u "
                    "JOIN runtime.file_objects f USING(file_id) WHERE u.principal_id=:owner "
                    "AND u.state='ready' AND f.category='original' "
                    "AND u.file_id=ANY(CAST(:ids AS uuid[]))"
                ),
                {"owner": str(owner), "ids": file_ids},
            )
            return {row["file_id"]: row for row in result.mappings()}
