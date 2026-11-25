"""登记和接收有限流式上传，文件完整发布后才保存完成状态。

分层定位：foundation（公共运行底座 / 文件上传）
对外契约：FileUploads 受理上传登记、流式接收、内容校验与完成/失败状态落定。
边界约束：业务用途权限由入口核对；本层只持短事务与有限文件资源，并发接收受信号量限制；
完整通过校验并登记后才置 ready。
"""

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

# 允许上传的原始文件媒体类型。
type OriginalMedia = Literal["application/pdf", "image/png", "image/jpeg"]
# 兼容宽松 UUID 解析的字段类型。
type JsonUUID = Annotated[UUID, Field(strict=False)]
# 各媒体类型的单文件大小上限。
MAX_BYTES: dict[str, int] = {
    "application/pdf": 512 * 1024 * 1024,
    "image/png": 32 * 1024 * 1024,
    "image/jpeg": 32 * 1024 * 1024,
}


class FileReceipt(FactModel):
    """上传完成后回传的文件收据：身份、类型、大小与摘要。"""

    storage_ref: JsonUUID
    media_type: OriginalMedia
    byte_size: Annotated[int, Field(gt=0)]
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class UploadView(FactModel):
    """上传记录视图：状态、完成收据或错误明细。"""

    upload_id: UUID
    state: Literal["receiving", "ready", "failed"]
    receipt: FileReceipt | None = None
    error: ErrorDetail | None = None


# 按上传编号与上传人查询上传记录及其已登记文件的 SQL。
_UPLOAD = text(
    "SELECT u.*, f.byte_size, f.sha256 FROM runtime.file_uploads u "
    "LEFT JOIN runtime.file_objects f USING (file_id) "
    "WHERE u.upload_id=:id AND u.principal_id=:owner"
)


def file_view(row: RowMapping | Mapping[str, Any]) -> FileReceipt:
    """把查询行映射为文件收据。"""
    return FileReceipt(
        storage_ref=row["file_id"],
        media_type=row["declared_media_type"],
        byte_size=row["byte_size"],
        sha256=row["sha256"],
    )


def upload_view(row: RowMapping) -> UploadView:
    """把查询行映射为上传视图；仅 ready 状态附带文件收据。"""
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
        """登记一次上传申请；同请求键幂等返回，异范围、异名称/类型/大小判冲突。"""
        # 大小必须为正且不超过该媒体类型的单文件上限。
        if not 0 < size <= MAX_BYTES[media]:
            raise RequestError(413, "payload_too_large", "文件大小超出此格式的上限。")
        # 有关联导入记录时记其引用，否则留空。
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
        # 同请求键已存在：范围不一致，或名称/类型/大小被改动，判请求冲突。
        if (
            not row["same_scope"]
            or row["original_name"] != name
            or row["declared_media_type"] != media
            or row["declared_size"] != size
        ):
            raise RequestError(409, "request_conflict", "同一上传编号已用于另一份文件或范围。")
        return upload_view(row)

    async def read(self, owner: UUID, upload_id: UUID) -> RowMapping:
        """按上传人查询上传记录；记录不存在则返回 404。"""
        async with self.engine.connect() as connection:
            row = (
                (await connection.execute(_UPLOAD, {"id": upload_id, "owner": str(owner)}))
                .mappings()
                .one_or_none()
            )
        # 记录不存在或不属于该上传人，按 404 处理。
        if row is None:
            raise RequestError(404, "not_found", "找不到上传记录。")
        return row

    async def _renew(self, upload_id: UUID, attempt: UUID) -> None:
        """续期本次写入租约；租约已过期或被其他尝试占用则拒绝。"""
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
        # 租约已过期或被其他尝试占用，续期失败，拒绝继续写入。
        if renewed is None:
            raise RequestError(409, "upload_busy", "上传已过期，请重新发送文件。")

    async def write(
        self, owner: UUID, row: RowMapping, media: str, chunks: AsyncIterator[bytes]
    ) -> UploadView:
        """复用原上传身份，核对实际大小及内容，保存已完成收据。"""
        upload_id: UUID = row["upload_id"]
        # 实际类型与登记类型不符，拒绝接收。
        if media != row["declared_media_type"]:
            raise RequestError(415, "unsupported_media_type", "文件类型与登记不符。")
        # 并发接收槽已满，按限流拒绝，避免暂存文件与内存失控。
        if self.running.locked():
            raise RequestError(429, "upload_busy", "正在接收其他文件，请稍后重试。")
        async with self.running:
            return await self._receive(owner, row, upload_id, chunks)

    async def _receive(
        self, owner: UUID, row: RowMapping, upload_id: UUID, chunks: AsyncIterator[bytes]
    ) -> UploadView:
        """流式接收分片到暂存文件，核对大小与完整性；已就绪则比对摘要防异内容复用。"""
        ready = row["state"] == "ready"
        attempt = uuid4()
        keys = {"id": upload_id, "attempt": attempt}
        # 未就绪的上传先抢占写入租约；已就绪的走摘要比对复用，不再写暂存。
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
            # 租约被其他尝试持有或记录已就绪，抢占失败。
            if claimed is None:
                raise RequestError(409, "upload_busy", "文件正在上传，请先查询上传结果。")

        size: int = row["declared_size"]
        media: OriginalMedia = row["declared_media_type"]
        try:
            # 整次接收设总超时，避免挂起占用并发槽。
            async with asyncio.timeout(20 * 60):
                with TemporaryFile(mode="w+b") as source:
                    received = 0
                    renew_at = time.monotonic() + 30
                    digest = hashlib.sha256()
                    # 逐片读取上传流，累计字节并按需续期租约。
                    while True:
                        try:
                            # 单片读取超时，防止上游长期不发数据。
                            async with asyncio.timeout(60):
                                chunk = await anext(chunks)
                        except StopAsyncIteration:
                            break
                        received += len(chunk)
                        # 累计字节超过声明大小即拒绝，不继续落盘。
                        if received > size:
                            raise RequestError(413, "payload_too_large", "上传超过声明的字节数。")
                        if ready:
                            # 已就绪复用：只累加摘要，不写暂存文件。
                            digest.update(chunk)
                        else:
                            source.write(chunk)
                            # 每 30 秒续一次写入租约，防止长时间传输被判过期。
                            if time.monotonic() >= renew_at:
                                await self._renew(upload_id, attempt)
                                renew_at = time.monotonic() + 30
                    # 实际字节与声明大小不一致，文件不完整。
                    if received != size:
                        raise RequestError(
                            422, "source_unavailable", "文件字节不完整，请重新上传。"
                        )
                    if ready:
                        # 复用编号的内容摘要与原文件不符，判内容冲突。
                        if digest.hexdigest() != row["sha256"]:
                            raise RequestError(
                                409, "content_conflict", "此上传编号已有不同的文件。"
                            )
                        return upload_view(row)

                    pages, file = await self._check_and_save(source, media, size, upload_id)
                    await self._complete(owner, upload_id, attempt, pages, file)
        # 按异常类型归类为对外错误；未就绪的上传才落失败状态，已就绪复用不改原记录。
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
        """线程内完成内容检查并保存原件；shield 保护取消场景下不丢已落盘结果。"""
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
            # shield 保护：外层取消不打断线程内已开始的检查与保存。
            return await asyncio.shield(job)
        except asyncio.CancelledError:
            # 被取消时等待线程收尾，避免暂存文件与任务泄漏，再向上抛取消。
            await asyncio.gather(job, return_exceptions=True)
            raise

    async def _complete(
        self, owner: UUID, upload_id: UUID, attempt: UUID, pages: int, file: FileObject
    ) -> None:
        """在持租约事务内登记文件并把上传置为 ready；租约失效则拒绝收尾。"""
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
            # 租约失效或尝试已变更，拒绝把本次结果收尾为 ready。
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
        """把本次上传落定为失败状态，记录错误明细与是否可重试。"""
        # 仅服务端临时故障（503）标记为可重试，其余错误不允许自动重试。
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
            # 按文件编号汇总为只读映射，业务模块还须再核对导入范围。
            return {row["file_id"]: row for row in result.mappings()}
