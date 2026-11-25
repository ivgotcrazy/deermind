"""事务外准备事实附件；先存字节和文件登记，再供业务事务引用。

分层定位：foundation（公共运行底座 / 事件附件）
对外契约：FactAttachments 提供 JSON 附件保存、按所有者读取与事件正文外置准备。
边界约束：访问范围先由事件登记校验；只返回身份引用，不授予裸 file_id 读取权限；
大正文在事务外固化，不在持锁时写文件。
"""

import asyncio
import hashlib
import io
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    INLINE_LIMIT,
    EventDraft,
    FactRecord,
    FileContent,
    InlineContent,
    PreparedEvents,
    ProducerAccess,
    Ref,
)
from deermind.abstractions.file_records import FileObject
from deermind.abstractions.files import FileStorage
from deermind.foundation.system.events.store import EventStore
from deermind.foundation.system.files.registry import FileRegistry
from pydantic import JsonValue, TypeAdapter
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine


class FactAttachments:
    """由受信业务调用；访问范围先由事件登记校验，不接受浏览器裸file_id读取。"""

    def __init__(self, engine: AsyncEngine, files: FileStorage) -> None:
        self.files = files
        self.registry = FileRegistry(engine)

    async def save_json(
        self,
        content: dict[str, JsonValue],
        *,
        actor: Ref,
        source: Ref,
        artifact_key: str,
        max_bytes: int,
    ) -> Ref:
        """为已授权所有者保存固定JSON附件；只返回身份，不授予读取权限。"""
        encoded = canonical_json(content).encode("utf-8")
        # 上限未配置或编码后超出上限，拒绝落附件。
        if max_bytes <= 0 or len(encoded) > max_bytes:
            raise ValueError("Fact attachment exceeds its limit")
        file = await self._save(encoded, actor, source, artifact_key)
        return Ref(owner="runtime", type="file", id=str(file.file_id))

    async def read_json(
        self, reference: Ref, *, source: Ref, max_bytes: int
    ) -> dict[str, JsonValue]:
        """调用者先核验业务权限；这里只允许同一所有者的完整附件，校验hash后解码。"""
        # 只接受 runtime 名下文件引用且读取上限为正，拒绝裸引用与越界读取。
        if reference.owner != "runtime" or reference.type != "file" or max_bytes <= 0:
            raise ValueError("Expected a bounded fact attachment read")
        file = await self.registry.by_id(UUID(reference.id))
        # 登记记录缺失，不能凭引用直接读后端字节。
        if file is None:
            raise FileNotFoundError("Fact attachment registration is missing")
        # 归属所有者、fact 类别与后端任一不符，判跨所有者或跨后端读取。
        if (
            file.source_refs != [source]
            or file.category != "fact"
            or file.backend != self.files.backend
        ):
            raise PermissionError("Attachment belongs to another owner or backend")
        content = await asyncio.to_thread(self.files.read, file.bytes_ref(), max_bytes=max_bytes)
        return TypeAdapter(dict[str, JsonValue]).validate_json(content, strict=True)

    async def prepare(
        self,
        store: EventStore,
        access: ProducerAccess,
        drafts: tuple[EventDraft, ...],
    ) -> PreparedEvents:
        """校验完整DTO后外置；任何失败都不开始业务事务，已登记文件仍保留。"""
        validated = store.validate_inline(access, drafts)
        prepared: list[EventDraft] = []
        decoded: list[str] = []
        # 逐条事件外置其过大正文；validate_inline 已先核验完整 DTO。
        for draft, (_, payload) in zip(drafts, validated, strict=True):
            records: list[FactRecord] = []
            # 逐条事实记录判断保留内联还是转为文件附件。
            for record in payload.records:
                # 准备阶段只接受内联正文，残留未解附件说明前置校验未过。
                if not isinstance(record.content, InlineContent):
                    raise ValueError("Preparation requires a complete inline DTO")
                content = canonical_json(record.content.value).encode("utf-8")
                # 小正文保留内联，直接收进记录。
                if len(content) <= INLINE_LIMIT:
                    records.append(record)
                    continue
                # 超过内联上限：先在事务外固化为文件，再用文件引用替换正文。
                file = await self._save(
                    content,
                    access.actor_ref,
                    draft.owner_ref,
                    f"fact:{draft.event_id}:{record.record_id}",
                )
                records.append(
                    record.model_copy(
                        update={
                            "content": FileContent(
                                storage="file",
                                file_id=file.file_id,
                                sha256=file.sha256,
                                media_type="application/json",
                            )
                        }
                    )
                )
            wire = payload.model_copy(update={"records": records})
            prepared.append(replace(draft, payload=wire.model_dump(mode="json")))
            decoded.append(payload.model_dump_json())
        return PreparedEvents(tuple(prepared), tuple(decoded), access)

    async def _save(
        self,
        content: bytes,
        actor: Ref,
        source: Ref,
        artifact_key: str,
    ) -> FileObject:
        """保存附件字节并登记文件；命中既有 artifact_key 时复用并重新核验内容。"""
        digest = hashlib.sha256(content).hexdigest()
        existing = await self.registry.by_artifact(artifact_key)
        # 命中既有工件：复用前核验内容、归属与后端一致。
        if existing is not None:
            return await asyncio.to_thread(self._check_existing, existing, content, digest, source)

        saved = await asyncio.to_thread(
            self.files.save,
            io.BytesIO(content),
            max_bytes=max(1, len(content)),
        )
        # 实际回读核验后才登记FileReceived，不能只凭写入返回值宣称完整保存。
        restored = await asyncio.to_thread(self.files.read, saved, max_bytes=len(content))
        # 回读字节与原正文不符，判存储不一致，放弃登记。
        if restored != content:
            raise OSError("Prepared attachment does not match its DTO")
        file = FileObject(
            file_id=saved.file_id,
            backend=self.files.backend,
            storage_key=saved.storage_key,
            media_type="application/json",
            byte_size=saved.byte_size,
            sha256=saved.sha256,
            category="fact",
            artifact_key=artifact_key,
            source_refs=[source],
            transform_ref=Ref(owner="runtime", type="encoding", id="canonical-json", version=1),
            created_at=datetime.now(UTC),
        )
        try:
            await self.registry.register(file, actor)
        except IntegrityError:
            # 并发以已提交登记为准，复用前重新核验。
            existing = await self.registry.by_artifact(artifact_key)
            # 冲突后仍查不到登记记录，属异常，向上抛。
            if existing is None:
                raise
            return await asyncio.to_thread(self._check_existing, existing, content, digest, source)
        return file

    def _check_existing(
        self,
        file: FileObject,
        content: bytes,
        digest: str,
        source: Ref,
    ) -> FileObject:
        """核验既有文件与本次内容、归属、后端、摘要一致后复用。"""
        # 后端、摘要、字节数、归属、类别、媒体类型与编码变换任一不符，判身份冲突。
        if (
            file.backend != self.files.backend
            or file.sha256 != digest
            or file.byte_size != len(content)
            or file.source_refs != [source]
            or file.category != "fact"
            or file.media_type != "application/json"
            or file.transform_ref
            != Ref(
                owner="runtime",
                type="encoding",
                id="canonical-json",
                version=1,
            )
        ):
            raise ValueError("File artifact identity conflicts with existing content")
        # 再从后端回读一次，确认既有字节与本次内容一致后才复用。
        if self.files.read(file.bytes_ref(), max_bytes=len(content)) != content:
            raise OSError("Existing file differs from its registered content")
        return file
