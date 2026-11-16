"""真实PG的授权读取与分页用例；仅随机测试库和临时文件，不新增业务页面。"""

import asyncio
import json
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from deermind.bootstrap.events import event_reader
from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.contracts import EventDraft, ProducerAccess, Ref
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.reading import (
    EventFilter,
    EventPartRef,
    ReadAccess,
)
from deermind.foundation.system.events.store import EventStore
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.files.local import LocalFiles
from deermind.product.accounts.save import save_initial_account
from event_read_fixture import HANDLERS, POLICIES, REGISTRATIONS
from pydantic import JsonValue, TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from test_database import DatabaseTestCase

ITEMS = TypeAdapter(list[dict[str, JsonValue]])
OBJECT = TypeAdapter(dict[str, JsonValue])


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
        self.access = ReadAccess(
            "student-one",
            "test.student",
            "product",
            "student_history",
            "authorized-request",
            frozenset({("learning_space", self.scope)}),
        )

    def reader(self, engine: AsyncEngine) -> EventReader:
        return EventReader(
            engine,
            self.files,
            REGISTRATIONS,
            HANDLERS,
            POLICIES,
            cursor_key=b"fixed-test-signing-key-not-a-secret",
        )

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
            await store.append_and_project(
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

    def test_snapshot_cursor_and_private_list(self) -> None:
        asyncio.run(self.with_engine(self.snapshot_cursor))

    async def snapshot_cursor(self, engine: AsyncEngine) -> None:
        first = await self.append(engine)
        await self.append(engine, private=True)
        third = await self.append(engine)
        reader = self.reader(engine)
        page = await reader.query_events(self.access, "learning_space", self.scope, limit=1)
        self.assertEqual(page["upper_seq"], 3)
        encoded = json.dumps(page, ensure_ascii=False)
        self.assertNotIn("PRIVATE", encoded)
        self.assertNotIn("payload", encoded)
        self.assertNotIn("records", encoded)
        cursor = page["next_cursor"]
        self.assertIsInstance(cursor, str)
        assert isinstance(cursor, str)
        await self.append(engine, body="分页后才写入")
        middle = await reader.query_events(
            self.access, "learning_space", self.scope, cursor=cursor, limit=1
        )
        self.assertEqual(middle["items"], [])
        next_cursor = middle["next_cursor"]
        assert isinstance(next_cursor, str)
        last = await reader.query_events(
            self.access, "learning_space", self.scope, cursor=next_cursor
        )
        self.assertEqual(last["upper_seq"], 3)
        self.assertIsNone(last["next_cursor"])
        self.assertEqual([item["event_id"] for item in items(last)], [str(third.event_id)])
        self.assertNotEqual(first.event_id, third.event_id)
        fresh = await reader.query_events(self.access, "learning_space", self.scope)
        self.assertEqual(fresh["upper_seq"], 4)

    def test_cursor_rejects_identity_filter_scope_and_signature_changes(self) -> None:
        asyncio.run(self.with_engine(self.cursor_rejections))

    async def cursor_rejections(self, engine: AsyncEngine) -> None:
        await self.append(engine)
        await self.append(engine)
        reader = self.reader(engine)
        page = await reader.query_events(self.access, "learning_space", self.scope, limit=1)
        cursor = page["next_cursor"]
        assert isinstance(cursor, str)
        for access, filters, token in (
            (replace(self.access, principal_id="another"), EventFilter(), cursor),
            (replace(self.access, authorization_ref="new-authorization"), EventFilter(), cursor),
            (self.access, EventFilter(event_types=("TestChatRecorded",)), cursor),
            (self.access, EventFilter(), "!" + cursor[1:]),
        ):
            with self.assertRaises(ValueError):
                await reader.query_events(
                    access, "learning_space", self.scope, filters=filters, cursor=token
                )
        with self.assertRaises(PermissionError):
            await reader.query_events(
                self.access, "learning_space", self.other_scope, cursor=cursor
            )

    def test_fields_purpose_and_scope_cannot_be_bypassed(self) -> None:
        asyncio.run(self.with_engine(self.denied_reads))

    async def denied_reads(self, engine: AsyncEngine) -> None:
        own = await self.append(engine, body="大" * 12000)
        other = await self.append(engine, scope=self.other_scope)
        private = await self.append(engine, private=True)
        reader = self.reader(engine)
        ref = EventPartRef(event_id=own.event_id, record_id="message", path="")
        for reference in (
            ref.model_copy(update={"path": "/secret"}),
            ref.model_copy(update={"event_id": other.event_id}),
            ref.model_copy(update={"event_id": private.event_id}),
        ):
            with patch.object(
                self.files, "read", side_effect=AssertionError("must not read")
            ) as read:
                with self.assertRaises(PermissionError):
                    await reader.read_event_facts(
                        self.access, [reference], purpose="student_history"
                    )
                read.assert_not_called()
        with self.assertRaises(PermissionError):
            await reader.read_event_facts(self.access, [ref], purpose="projection_rebuild")
        with self.assertRaises(PermissionError):
            await reader.read_event_facts(
                replace(self.access, handler_id="unknown"), [ref], purpose="student_history"
            )
        allowed = await reader.read_event_facts(self.access, [ref], purpose="student_history")
        self.assertNotIn("PRIVATE", json.dumps(allowed))
        self.assertNotIn("storage_key", json.dumps(allowed))
        self.assertNotIn('"storage":', json.dumps(allowed))
        self.assertEqual(items(allowed)[0]["visibility"], "partial")
        self.assertEqual(items(allowed)[0]["completeness"], "complete")
        payload = ref.model_copy(update={"record_id": None, "path": ""})
        result = await reader.read_event_facts(self.access, [payload], purpose="student_history")
        self.assertEqual(items(result)[0]["content"], {"action": "recorded"})
        with self.assertRaises(PermissionError):
            await reader.read_event_facts(
                self.access,
                [payload.model_copy(update={"path": "/records"})],
                purpose="student_history",
            )

    def test_source_reference_requires_fresh_authorization(self) -> None:
        asyncio.run(self.with_engine(self.source_reference))

    async def source_reference(self, engine: AsyncEngine) -> None:
        other = await self.append(engine, scope=self.other_scope)
        source = EventPartRef(event_id=other.event_id, record_id="message", path="/body")
        own = await self.append(engine, source=source)
        reader = self.reader(engine)
        result = await reader.read_event_facts(
            self.access,
            [EventPartRef(event_id=own.event_id, record_id="message", path="/source")],
            purpose="student_history",
        )
        self.assertEqual(items(result)[0]["content"], source.model_dump(mode="json"))
        with self.assertRaises(PermissionError):
            await reader.read_event_facts(self.access, [source], purpose="student_history")

    def test_continuous_scan_advances_over_filtered_events(self) -> None:
        asyncio.run(self.with_engine(self.scan_progress))

    async def scan_progress(self, engine: AsyncEngine) -> None:
        await self.append(engine, private=True)
        await self.append(engine, private=True)
        last = await self.append(engine)
        access = replace(
            self.access,
            handler_id="test.maintenance",
            module="runtime",
            purpose="projection_rebuild",
            maintenance_ref="approved-maintenance",
        )
        reader = self.reader(engine)
        first = await reader.read_scope_events(
            access, "learning_space", self.scope, after_seq=0, types=("TestChatRecorded",), limit=2
        )
        self.assertEqual(first["items"], [])
        self.assertEqual(first["scanned_through_seq"], 2)
        await self.append(engine)
        second = await reader.read_scope_events(
            access,
            "learning_space",
            self.scope,
            after_seq=2,
            through_seq=3,
            types=("TestChatRecorded",),
        )
        self.assertEqual(second["scanned_through_seq"], 3)
        self.assertEqual(items(second)[0]["event_id"], str(last.event_id))
        with self.assertRaises(PermissionError):
            await reader.read_scope_events(self.access, "learning_space", self.scope, after_seq=0)

    def test_attachment_faults_are_not_empty_success(self) -> None:
        asyncio.run(self.with_engine(self.attachment_faults))

    async def attachment_faults(self, engine: AsyncEngine) -> None:
        draft = await self.append(engine, body="x" * 33000)
        ref = EventPartRef(event_id=draft.event_id, record_id="message", path="/body")
        reader = self.reader(engine)
        result = await reader.read_event_facts(self.access, [ref], purpose="student_history")
        self.assertEqual(items(result)[0]["content"], "x" * 33000)
        file = next(self.files.root.glob("*.blob"))
        content = file.read_bytes()
        file.chmod(0o600)
        file.write_bytes(b"!" + content[1:])
        with self.assertRaises(OSError):
            await reader.read_event_facts(self.access, [ref], purpose="student_history")
        file.unlink()
        with self.assertRaises(OSError):
            await reader.read_event_facts(self.access, [ref], purpose="student_history")

    def test_evaluation_requires_source_and_resource_bounds(self) -> None:
        asyncio.run(self.with_engine(self.evaluation_bounds))

    async def evaluation_bounds(self, engine: AsyncEngine) -> None:
        own = await self.append(engine)
        other = await self.append(engine)
        reader = self.reader(engine)
        access = replace(
            self.access,
            handler_id="test.evaluation",
            module="evaluation",
            purpose="evaluation_basis",
        )
        ref = EventPartRef(event_id=own.event_id, record_id="message", path="/body")
        with self.assertRaises(PermissionError):
            await reader.read_event_facts(access, [ref], purpose="evaluation_basis")
        access = replace(
            access, source_event_ids=frozenset({own.event_id}), resource_refs=(own.owner_ref,)
        )
        result = await reader.read_event_facts(access, [ref], purpose="evaluation_basis")
        self.assertEqual(items(result)[0]["content"], "可见原文")
        for narrowed in (
            replace(access, source_event_ids=frozenset({other.event_id})),
            replace(access, resource_refs=(other.owner_ref,)),
        ):
            with self.assertRaises(PermissionError):
                await reader.read_event_facts(narrowed, [ref], purpose="evaluation_basis")

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
        result = await reader.query_events(
            self.access, "learning_space", self.scope, filters=filters
        )
        self.assertEqual([item["event_id"] for item in items(result)], [str(first.event_id)])
        for limit in (0, 101, True):
            with self.assertRaises(ValueError):
                await reader.query_events(self.access, "learning_space", self.scope, limit=limit)
        with self.assertRaises(ValueError):
            await reader.query_events(
                self.access,
                "learning_space",
                self.scope,
                filters=EventFilter(recorded_from=datetime(2026, 1, 1)),
            )

    def test_real_account_requires_authorized_maintenance(self) -> None:
        asyncio.run(self.with_engine(self.real_account))

    async def real_account(self, engine: AsyncEngine) -> None:
        from deermind.bootstrap.events import event_store

        identity = uuid4()
        access = ProducerAccess(
            "product",
            Ref(owner="runtime", type="service", id="test"),
            frozenset({("account", identity)}),
        )
        await save_initial_account(
            engine,
            event_store(),
            access,
            request_id="account",
            account_id=identity,
            login_identifier="test",
            display_name="账号",
        )
        async with engine.connect() as connection:
            event_id = await connection.scalar(text("SELECT event_id FROM runtime.events"))
        reader = event_reader(engine, self.files, cursor_key=b"fixed-test-signing-key-not-a-secret")
        authorized = ReadAccess(
            "operator",
            "runtime.projection_read",
            "runtime",
            "projection_rebuild",
            "approved-maintenance",
            frozenset({("account", identity)}),
            maintenance_ref="maintenance-1",
        )
        ref = EventPartRef(event_id=event_id, record_id="account", path="")
        result = await reader.read_event_facts(authorized, [ref], purpose="projection_rebuild")
        restored = await reader.read_projection_event(authorized, event_id)
        self.assertEqual(restored.draft.event_id, event_id)
        self.assertEqual(restored.draft.scope_id, identity)
        self.assertEqual(restored.payload.records[0].record_type, "product.accounts")
        self.assertEqual(
            OBJECT.validate_python(items(result)[0]["content"], strict=True)["display_name"], "账号"
        )
        with self.assertRaises(PermissionError):
            await reader.read_event_facts(
                replace(authorized, maintenance_ref=None), [ref], purpose="projection_rebuild"
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
            await reader.read_event_facts(self.access, [ref] * 4, purpose="student_history")
        small = ref.model_copy(update={"path": "/source"})
        with self.assertRaises(ValueError):
            await reader.read_event_facts(self.access, [small] * 32, purpose="student_history")
        # 失败不消耗事实，也不推进外部进度；缩小范围后可重新取得完整正文。
        result = await reader.read_event_facts(self.access, [ref], purpose="student_history")
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
            await reader.read_event_facts(self.access, [ref], purpose="student_history")
        with self.assertRaises(ValueError):
            await reader.read_event_facts(
                self.access,
                [ref.model_copy(update={"record_id": "missing"})],
                purpose="student_history",
            )
        result = await reader.read_event_facts(
            self.access,
            [ref.model_copy(update={"path": "/source/unknown"})],
            purpose="student_history",
        )
        self.assertEqual(items(result)[0]["completeness"], "incomplete")
        self.assertEqual(items(result)[0]["missing_reasons"], ["field_missing"])
        self.assertIsNone(items(result)[0]["content"])

    def test_file_registration_only_opens_to_authorized_maintenance(self) -> None:
        asyncio.run(self.with_engine(self.file_registration))

    async def file_registration(self, engine: AsyncEngine) -> None:
        await self.append(engine, body="x" * 33000)
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT event_id, scope_id FROM runtime.events "
                        "WHERE event_type='FileReceived'"
                    )
                )
            ).one()
        reader = event_reader(engine, self.files, cursor_key=b"fixed-test-signing-key-not-a-secret")
        access = ReadAccess(
            "operator",
            "runtime.file_review",
            "runtime",
            "execution_support",
            "authorized-maintenance",
            frozenset({("file", row.scope_id)}),
            maintenance_ref="maintenance-1",
        )
        ref = EventPartRef(event_id=row.event_id, record_id="file", path="")
        result = await reader.read_event_facts(access, [ref], purpose="execution_support")
        content = OBJECT.validate_python(items(result)[0]["content"], strict=True)
        self.assertEqual(content["file_id"], str(row.scope_id))
        self.assertEqual(content["category"], "fact")
        with self.assertRaises(PermissionError):
            await reader.read_event_facts(
                replace(access, maintenance_ref=None, execution_ref=uuid4()),
                [ref],
                purpose="execution_support",
            )
