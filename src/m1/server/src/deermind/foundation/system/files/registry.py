"""文件登记与 FileReceived 事实在同一短事务提交。"""

from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, FactRecord, InlineContent, ProducerAccess, Ref
from deermind.abstractions.file_records import FileObject, FileReceived
from deermind.foundation.system.events.store import EventStore
from deermind.foundation.system.files.records import FILE_REGISTRATION, project_file
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class FileRegistry:
    """读取文件登记，原子保存已核验的登记事实和查询投影。"""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.events = EventStore([FILE_REGISTRATION])

    async def by_artifact(self, key: str) -> FileObject | None:
        """按不可变产物身份定位登记。"""
        return await self._find("artifact_key", key)

    async def by_id(self, file_id: UUID) -> FileObject | None:
        """按固定文件身份定位登记。"""
        return await self._find("file_id", file_id)

    async def _find(self, field: str, identity: UUID | str) -> FileObject | None:
        # field 只来自本类两个固定入口，实际查找值通过 SQL 参数传入。
        async with self.engine.connect() as connection:
            row = await connection.scalar(
                text(f"SELECT to_jsonb(f) FROM runtime.file_objects f WHERE {field}=:identity"),
                {"identity": identity},
            )
        if row is None:
            return None
        return FileObject.model_validate_json(canonical_json(row))

    async def register(self, file: FileObject, actor: Ref) -> None:
        """先追加文件事实，再写同一份文件登记。"""
        async with self.engine.begin() as connection:
            await self.register_in(connection, file, actor)

    async def register_in(
        self,
        connection: AsyncConnection,
        file: FileObject,
        actor: Ref,
        *,
        source_request_id: str | None = None,
    ) -> None:
        """调用方已持有事务时，文件登记可与上传完成状态一起提交。"""
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
        events = await self.events.append(
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
                    source_request_id=source_request_id or file.artifact_key,
                    subject_refs=tuple(file.source_refs),
                )
            ],
            commit_id=uuid4(),
            correlation_id=file.file_id,
            expected_seq={("file", file.file_id): 0},
        )
        await project_file(connection, events[0])
