"""真实PG的显式条件读取与分页用例；仅随机测试库和临时文件，不新增业务页面。"""

import asyncio
import json
import tempfile
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from deermind.abstractions.event_reading import EventFilter, EventPartRef
from deermind.abstractions.events import EventDraft, ProducerAccess, Ref
from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.files.local import LocalFiles
from event_read_fixture import REGISTRATIONS
from pydantic import JsonValue, TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from test_database import DatabaseTestCase

ITEMS = TypeAdapter(list[dict[str, JsonValue]])


def items(response: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
    """验证返回形状，再断言具体业务值，不通过强制转换跳过校验。"""
    return ITEMS.validate_python(response["items"], strict=True)


class EventReadTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.files = LocalFiles(Path(temporary.name), backend="local")
        self.scope = uuid4()
        self.other_scope = uuid4()

    def reader(self, engine: AsyncEngine) -> EventReader:
        return EventReader(engine, self.files, REGISTRATIONS)

    async def append(
        self,
        engine: AsyncEngine,
        *,
        body: str = "可见原文",
        private: bool = False,
        scope: UUID | None = None,
        source: EventPartRef | None = None,
    ) -> EventDraft:
        scope = scope or self.scope
        draft = EventDraft(
            event_id=uuid4(),
            event_type="TestPrivateRecorded" if private else "TestChatRecorded",
            schema_version=1,
            scope_kind="learning_space",
            scope_id=scope,
            owner_ref=Ref(owner="interaction", type="message", id=str(uuid4())),
            source_request_id="read-test",
            payload={
                "action": "recorded",
                "hidden_reason": "PRIVATE-PAYLOAD",
                "records": [
                    {
                        "record_id": "message",
                        "record_type": "test.messages",
                        "schema_version": 1,
                        "content": {
                            "storage": "inline",
                            "value": {
                                "body": body,
                                "secret": "PRIVATE-BODY",
                                "source": source.model_dump(mode="json") if source else None,
                            },
                        },
                    }
                ],
            },
        )
        access = ProducerAccess(
            "interaction",
            Ref(owner="runtime", type="service", id="test"),
            frozenset({("learning_space", scope)}),
        )
        store = EventStore(REGISTRATIONS)
        prepared = await FactAttachments(engine, self.files).prepare(store, access, (draft,))
        async with engine.begin() as connection:
            previous = await connection.scalar(
                text(
                    "SELECT last_seq FROM runtime.scope_event_heads "
                    "WHERE scope_kind='learning_space' "
                    "AND scope_id=:scope"
                ),
                {"scope": scope},
            )
            await store.append(
                connection,
                access,
                prepared,
                commit_id=uuid4(),
                correlation_id=uuid4(),
                expected_seq={("learning_space", scope): previous or 0},
            )
        return draft

    async def with_engine(self, scenario: Callable[[AsyncEngine], Awaitable[None]]) -> None:
        """每个场景独立引擎，避免连接跨asyncio事件循环复用。"""
        engine = application_engine(self.app)
        try:
            await scenario(engine)
        finally:
            await engine.dispose()

    def test_metadata_uses_fixed_upper_and_explicit_filter(self) -> None:
        asyncio.run(self.with_engine(self.snapshot))

    async def snapshot(self, engine: AsyncEngine) -> None:
        await self.append(engine)
        await self.append(engine, private=True)
        third = await self.append(engine)
        reader = self.reader(engine)
        filters = EventFilter(event_types=("TestChatRecorded",))
        first = await reader.query_metadata("learning_space", self.scope, filters=filters, limit=1)
        self.assertEqual((first["next_after_seq"], first["upper_seq"]), (1, 3))
        self.assertNotIn("payload", items(first)[0])
        self.assertNotIn("PRIVATE", json.dumps(first))
        await self.append(engine)
        last = await reader.query_metadata(
            "learning_space", self.scope, filters=filters, upper_seq=3, after_seq=1
        )
        self.assertEqual([r["event_id"] for r in items(last)], [str(third.event_id)])
        self.assertIsNone(last["next_after_seq"])

    def test_constraints_checked_before_attachment_io(self) -> None:
        asyncio.run(self.with_engine(self.constrained))

    async def constrained(self, engine: AsyncEngine) -> None:
        own = await self.append(engine, body="x" * 33000)
        ref = EventPartRef(event_id=own.event_id, record_id="message", path="/body")
        reader = self.reader(engine)
        with patch.object(self.files, "read", side_effect=AssertionError("must not open blob")):
            for scope, event_type, version, correlation in (
                (self.other_scope, own.event_type, 1, None),
                (self.scope, "TestPrivateRecorded", 1, None),
                (self.scope, own.event_type, 2, None),
                (self.scope, own.event_type, 1, uuid4()),
            ):
                with self.assertRaises(LookupError):
                    await reader.read_facts(
                        "learning_space",
                        scope,
                        own.event_id,
                        refs=[ref],
                        expected_event_type=event_type,
                        schema_version=version,
                        correlation_id=correlation,
                    )
            for invalid in (
                ref.model_copy(update={"record_id": None, "path": "/records/0"}),
                ref.model_copy(update={"event_id": uuid4()}),
            ):
                with self.assertRaises(ValueError):
                    await reader.read_facts(
                        "learning_space", self.scope, own.event_id, refs=[invalid]
                    )
            action = ref.model_copy(update={"record_id": None, "path": "/action"})
            response = await reader.read_facts(
                "learning_space", self.scope, own.event_id, refs=[action]
            )
            self.assertEqual(items(response)[0]["content"], "recorded")

    def test_source_reference_requires_fresh_authorization(self) -> None:
        asyncio.run(self.with_engine(self.source_reference))

    async def source_reference(self, engine: AsyncEngine) -> None:
        other = await self.append(engine, scope=self.other_scope)
        source = EventPartRef(event_id=other.event_id, record_id="message", path="/body")
        own = await self.append(engine, source=source)
        reader = self.reader(engine)
        result = await reader.read_facts(
            "learning_space",
            self.scope,
            own.event_id,
            refs=[EventPartRef(event_id=own.event_id, record_id="message", path="/source")],
        )
        self.assertEqual(items(result)[0]["content"], source.model_dump(mode="json"))
        with self.assertRaises(LookupError):
            await reader.read_facts("learning_space", self.scope, source.event_id, refs=[source])

    def test_scan_checks_every_sequence_before_filtering(self) -> None:
        asyncio.run(self.with_engine(self.scan))

    async def scan(self, engine: AsyncEngine) -> None:
        ignored = await self.append(engine, private=True, body="x" * 33000)
        selected = await self.append(engine)
        await self.append(engine)
        reader = self.reader(engine)
        types = frozenset({selected.event_type})
        async with engine.begin() as connection:
            with patch.object(self.files, "read", side_effect=AssertionError("irrelevant blob")):
                first = await reader.scan_scope(
                    connection,
                    "learning_space",
                    self.scope,
                    after_seq=0,
                    upper_seq=2,
                    types=types,
                    limit=1,
                )
                second = await reader.scan_scope(
                    connection,
                    "learning_space",
                    self.scope,
                    after_seq=first.scanned_through_seq,
                    upper_seq=2,
                    types=types,
                )
            self.assertEqual(first.events, ())
            self.assertEqual((first.scanned_through_seq, first.upper_seq), (1, 2))
            self.assertEqual([e.draft.event_id for e in second.events], [selected.event_id])
            self.assertEqual(second.scanned_through_seq, 2)
        with self.engine.begin() as admin:
            admin.execute(
                text("DELETE FROM runtime.events WHERE event_id=:id"), {"id": ignored.event_id}
            )
        async with engine.begin() as connection:
            with self.assertRaisesRegex(ValueError, "sequence is missing"):
                await reader.scan_scope(
                    connection, "learning_space", self.scope, after_seq=0, upper_seq=2, types=types
                )

    def test_attachment_faults_are_not_empty_success(self) -> None:
        asyncio.run(self.with_engine(self.attachment_faults))

    async def attachment_faults(self, engine: AsyncEngine) -> None:
        draft = await self.append(engine, body="x" * 33000)
        ref = EventPartRef(event_id=draft.event_id, record_id="message", path="/body")
        reader = self.reader(engine)
        result = await reader.read_facts("learning_space", self.scope, ref.event_id, refs=[ref])
        self.assertEqual(items(result)[0]["content"], "x" * 33000)
        file = next(self.files.root.glob("*.blob"))
        content = file.read_bytes()
        file.chmod(0o600)
        file.write_bytes(b"!" + content[1:])
        with self.assertRaises(OSError):
            await reader.read_facts("learning_space", self.scope, ref.event_id, refs=[ref])
        file.unlink()
        with self.assertRaises(OSError):
            await reader.read_facts("learning_space", self.scope, ref.event_id, refs=[ref])

    def test_filters_and_query_limits(self) -> None:
        asyncio.run(self.with_engine(self.query_filters))

    async def query_filters(self, engine: AsyncEngine) -> None:
        first = await self.append(engine)
        await self.append(engine)
        reader = self.reader(engine)
        filters = EventFilter(
            subject_ref=first.owner_ref,
            recorded_from=datetime.now(UTC) - timedelta(days=1),
            recorded_to=datetime.now(UTC) + timedelta(days=1),
        )
        result = await reader.query_metadata("learning_space", self.scope, filters=filters)
        self.assertEqual([item["event_id"] for item in items(result)], [str(first.event_id)])
        for limit in (0, 101, True):
            with self.assertRaises(ValueError):
                await reader.query_metadata("learning_space", self.scope, limit=limit)
        with self.assertRaises(ValueError):
            await reader.query_metadata(
                "learning_space",
                self.scope,
                filters=EventFilter(recorded_from=datetime(2026, 1, 1)),
            )

    def test_response_and_decoded_content_limits_do_not_truncate(self) -> None:
        asyncio.run(self.with_engine(self.content_limits))

    async def content_limits(self, engine: AsyncEngine) -> None:
        # 同一事实可取不同字段；读取预算按完整解包量累计，响应预算按返回量计算。
        draft = await self.append(engine, body="x" * (1024 * 1024))
        reader = self.reader(engine)
        ref = EventPartRef(event_id=draft.event_id, record_id="message", path="/body")
        async with engine.connect() as connection:
            before = await connection.scalar(text("SELECT count(*) FROM runtime.events"))
        with self.assertRaisesRegex(ValueError, "Response exceeds 4MiB"):
            await reader.read_facts("learning_space", self.scope, ref.event_id, refs=[ref] * 4)
        small = ref.model_copy(update={"path": "/source"})
        with self.assertRaises(ValueError):
            await reader.read_facts("learning_space", self.scope, ref.event_id, refs=[small] * 32)
        # 失败不消耗事实，也不推进外部进度；缩小范围后可重新取得完整正文。
        result = await reader.read_facts("learning_space", self.scope, ref.event_id, refs=[ref])
        self.assertEqual(items(result)[0]["content"], "x" * (1024 * 1024))
        async with engine.connect() as connection:
            self.assertEqual(
                await connection.scalar(text("SELECT count(*) FROM runtime.events")), before
            )

    def test_missing_authorized_field_and_invalid_reference_are_distinct(self) -> None:
        asyncio.run(self.with_engine(self.missing_field))

    async def missing_field(self, engine: AsyncEngine) -> None:
        source = EventPartRef(event_id=uuid4(), record_id="message", path="/body")
        draft = await self.append(engine, source=source)
        reader = self.reader(engine)
        ref = EventPartRef(event_id=draft.event_id, record_id="message", path="/body/child")
        with self.assertRaises(ValueError):
            await reader.read_facts("learning_space", self.scope, ref.event_id, refs=[ref])
        with self.assertRaises(ValueError):
            await reader.read_facts(
                "learning_space",
                self.scope,
                ref.event_id,
                refs=[ref.model_copy(update={"record_id": "missing"})],
            )
        result = await reader.read_facts(
            "learning_space",
            self.scope,
            ref.event_id,
            refs=[ref.model_copy(update={"path": "/source/unknown"})],
        )
        self.assertEqual(items(result)[0]["completeness"], "incomplete")
        self.assertEqual(items(result)[0]["missing_reasons"], ["field_missing"])
        self.assertIsNone(items(result)[0]["content"])
