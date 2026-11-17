"""事务外准备事实附件；先存字节和文件登记，再供业务事务引用。"""

import asyncio
import hashlib
import io
import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

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
from deermind.abstractions.file_records import FileObject, FileReceived
from deermind.abstractions.files import FileStorage
from deermind.foundation.system.events.store import EventStore
from deermind.foundation.system.files.records import FILE_REGISTRATION, project_file
from pydantic import JsonValue, TypeAdapter
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine


class FactAttachments:
    """由受信业务调用；访问范围先由事件登记校验，不接受浏览器裸file_id读取。"""

    def __init__(self, engine: AsyncEngine, files: FileStorage) -> None:
        self.engine = engine
        self.files = files
        self._file_events = EventStore([FILE_REGISTRATION])

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
        if max_bytes <= 0 or len(encoded) > max_bytes:
            raise ValueError("Fact attachment exceeds its limit")
        file = await self._save(encoded, actor, source, artifact_key)
        return Ref(owner="runtime", type="file", id=str(file.file_id))

    async def read_json(
        self, reference: Ref, *, source: Ref, max_bytes: int
    ) -> dict[str, JsonValue]:
        """调用者先核验业务权限；这里只允许同一所有者的完整附件，校验hash后解码。"""
        if reference.owner != "runtime" or reference.type != "file" or max_bytes <= 0:
            raise ValueError("Expected a bounded fact attachment read")
        async with self.engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text("SELECT * FROM runtime.file_objects WHERE file_id=CAST(:id AS uuid)"),
                        {"id": reference.id},
                    )
                )
                .mappings()
                .one()
            )
        file = FileObject.model_validate_json(json.dumps(dict(row), default=str))
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
        for draft, (_, payload) in zip(drafts, validated, strict=True):
            records: list[FactRecord] = []
            for record in payload.records:
                if not isinstance(record.content, InlineContent):
                    raise ValueError("Preparation requires a complete inline DTO")
                content = canonical_json(record.content.value).encode("utf-8")
                if len(content) <= INLINE_LIMIT:
                    records.append(record)
                    continue
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

    async def _find(self, artifact_key: str) -> FileObject | None:
        async with self.engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text("SELECT * FROM runtime.file_objects WHERE artifact_key=:key"),
                        {"key": artifact_key},
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        # DB JSON中UUID为字符串，用固定JSON模式解码，仍拒绝额外字段。
        values = dict(row)
        values["file_id"] = str(values["file_id"])
        values["created_at"] = values["created_at"].isoformat()
        return FileObject.model_validate_json(canonical_json(values))

    async def _save(
        self,
        content: bytes,
        actor: Ref,
        source: Ref,
        artifact_key: str,
    ) -> FileObject:
        digest = hashlib.sha256(content).hexdigest()
        existing = await self._find(artifact_key)
        if existing is not None:
            return await asyncio.to_thread(self._check_existing, existing, content, digest, source)

        saved = await asyncio.to_thread(
            self.files.save,
            io.BytesIO(content),
            max_bytes=max(1, len(content)),
        )
        # 实际回读核验后才登记FileReceived，不能只凭写入返回值宣称完整保存。
        restored = await asyncio.to_thread(self.files.read, saved, max_bytes=len(content))
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
        owner = Ref(owner="runtime", type="file", id=str(file.file_id))
        payload = FileReceived(
            subject_ref=owner,
            outcome="recorded",
            reason_code=None,
            records=[
                FactRecord(
                    record_id="file",
                    record_type="runtime.file_objects",
                    schema_version=1,
                    content=InlineContent(storage="inline", value=file.model_dump(mode="json")),
                )
            ],
        )
        try:
            async with self.engine.begin() as connection:
                events = await self._file_events.append(
                    connection,
                    ProducerAccess("runtime", actor, frozenset({("file", file.file_id)})),
                    [
                        EventDraft(
                            event_id=uuid4(),
                            event_type="FileReceived",
                            schema_version=1,
                            scope_kind="file",
                            scope_id=file.file_id,
                            owner_ref=owner,
                            payload=payload.model_dump(mode="json"),
                            source_request_id=artifact_key,
                            subject_refs=(source,),
                        )
                    ],
                    commit_id=uuid4(),
                    correlation_id=file.file_id,
                    expected_seq={("file", file.file_id): 0},
                )
                await project_file(connection, events[0])
        except IntegrityError:
            # 同产物并发保存只认已提交的一份登记；失败尝试的文件不覆盖它。
            existing = await self._find(artifact_key)
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
        if self.files.read(file.bytes_ref(), max_bytes=len(content)) != content:
            raise OSError("Existing file differs from its registered content")
        return file
