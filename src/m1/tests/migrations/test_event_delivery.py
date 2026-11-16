"""隔离PG库和JetStream流中的交接测试；不使用真实学生数据或生产订阅。"""

import asyncio
import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.system.delivery.consumer import accept
from deermind.foundation.system.delivery.contracts import (
    Acceptance,
    DeliveryNotice,
    EventNotice,
    Subscription,
    SubscriptionRegistry,
)
from deermind.foundation.system.delivery.outbox import Outbox, claim, finish
from deermind.foundation.system.delivery.recovery import redeliver
from deermind.foundation.system.events.contracts import EventDraft, ProducerAccess, Ref
from deermind.foundation.system.events.store import EventStore
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.nats.bridge import (
    collect_one,
    consume_one,
    publish_one,
    reconcile,
)
from deermind.infrastructure.nats.connection import JetStream, MessagingSettings, connect
from deermind.product.accounts.facts import ACCOUNT_REGISTRATION, AccountFact
from nats.js.api import StreamConfig
from nats.js.errors import NotFoundError
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from test_database import DatabaseTestCase


class DeliveryTests(DatabaseTestCase):
    """只检验可靠交接；后续AI执行不属于此增量。"""

    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)
        self.scope_id = uuid4()
        self.calls = 0
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE product.delivery_test_work "
                    "(id uuid PRIMARY KEY,event_id uuid NOT NULL UNIQUE)"
                )
            )
            connection.execute(
                text("GRANT SELECT,INSERT ON product.delivery_test_work TO deermind_app")
            )
        self.subscription = Subscription(
            "test_receiver",
            "1",
            frozenset({"TrialAccountSaved"}),
            frozenset({"account"}),
            self.arrange_work,
        )
        self.registry = SubscriptionRegistry([self.subscription])
        self.store = EventStore(
            [ACCOUNT_REGISTRATION], arrange_delivery=Outbox(self.registry).arrange
        )

    async def arrange_work(self, connection: AsyncConnection, notice: EventNotice) -> Acceptance:
        """测试模块先持久保存工作；返回引用不等于执行成功。"""
        self.calls += 1
        identity = uuid4()
        await connection.execute(
            text("INSERT INTO product.delivery_test_work VALUES (:id,:event)"),
            {"id": identity, "event": notice.event_id},
        )
        return Acceptance(
            disposition="accepted",
            arrangement_refs=[Ref(owner="product", type="test_work", id=str(identity))],
        )

    async def append(self, connection: AsyncConnection) -> None:
        fact = AccountFact(
            account_id=self.scope_id,
            login_identifier=str(self.scope_id),
            display_name="交接测试",
            role="admin",
            status="active",
            revision=1,
            created_at=datetime.now(UTC),
        )
        scope = ("account", self.scope_id)
        await self.store.append_and_project(
            connection,
            ProducerAccess(
                "product", Ref(owner="runtime", type="service", id="test"), frozenset({scope})
            ),
            [
                EventDraft(
                    uuid4(),
                    "TrialAccountSaved",
                    1,
                    *scope,
                    Ref(owner="product", type="account", id=str(self.scope_id), revision=1),
                    {
                        "account_id": str(self.scope_id),
                        "action": "bootstrap_admin",
                        "account_revision": 1,
                        "relation_refs": [],
                        "records": [
                            {
                                "record_id": "account",
                                "record_type": "product.accounts",
                                "schema_version": 1,
                                "content": {
                                    "storage": "inline",
                                    "value": fact.model_dump(mode="json"),
                                },
                            }
                        ],
                    },
                    "delivery-test",
                )
            ],
            commit_id=uuid4(),
            correlation_id=uuid4(),
            expected_seq={scope: 0},
        )

    async def saved_notice(self, engine: AsyncEngine) -> EventNotice:
        async with engine.connect() as connection:
            body = await connection.scalar(
                text("SELECT payload FROM runtime.handoffs WHERE kind='publish'")
            )
            return EventNotice.model_validate_json(json.dumps(body))

    @asynccontextmanager
    async def fixture(self, *, save: bool = True) -> AsyncGenerator[AsyncEngine]:
        engine = application_engine(self.app)
        try:
            if save:
                async with engine.begin() as connection:
                    await self.append(connection)
            yield engine
        finally:
            await engine.dispose()

    @asynccontextmanager
    async def messaging(self) -> AsyncGenerator[JetStream]:
        """每例创建独立测试流；仅删除本例的随机前缀，不接触正式流。"""
        settings = MessagingSettings(
            address=os.environ["M1_TEST_NATS_ADDRESS"],
            deployment="test-" + uuid4().hex[:12],
            user="maintenance",
            password=SecretStr(os.environ["M1_TEST_NATS_PASSWORD"]),
        )
        async with connect(settings) as transport:
            production_config = transport.stream_config

            def test_config(*, failure: bool) -> StreamConfig:
                # 隔离用例只需少量消息，不能再次占用正式流的整套容量预留。
                return replace(production_config(failure=failure), max_bytes=1024 * 1024)

            with patch.object(transport, "stream_config", side_effect=test_config):
                try:
                    await transport.initialize(self.registry)
                    yield transport
                finally:
                    for stream in (settings.stream, settings.failures):
                        try:
                            await transport.js.delete_stream(stream)
                        except NotFoundError:
                            # 初始化可能只完成一部分；清理不应覆盖真正的失败原因。
                            pass

    def test_atomic_publication(self) -> None:
        """投影和发布安排随事务回滚；审计事实不递归生成发布安排。"""

        async def check() -> None:
            async with self.fixture(save=False) as engine:
                with self.assertRaisesRegex(RuntimeError, "rollback"):
                    async with engine.begin() as connection:
                        await self.append(connection)
                        raise RuntimeError("rollback")
                async with engine.connect() as connection:
                    for table in ("events", "handoffs", "projection_receipts"):
                        self.assertEqual(
                            await connection.scalar(text(f"SELECT count(*) FROM runtime.{table}")),
                            0,
                        )
                async with engine.begin() as connection:
                    await self.append(connection)
                async with engine.connect() as connection:
                    self.assertEqual(
                        await connection.scalar(text("SELECT count(*) FROM runtime.handoffs")), 1
                    )
                    self.assertEqual(
                        await connection.scalar(text("SELECT count(*) FROM runtime.events")), 2
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(DISTINCT commit_id) FROM runtime.events")
                        ),
                        1,
                    )

        asyncio.run(check())

    def test_rejection_is_saved_before_term(self) -> None:
        """明确拒绝保存收据和故障后才Term；通知再次到达不产生新工作。"""

        async def check() -> None:
            async def reject(connection: AsyncConnection, notice: EventNotice) -> Acceptance:
                return Acceptance(
                    disposition="rejected",
                    arrangement_refs=[],
                    error={"code": "NOT_SUPPORTED", "message": "测试拒绝"},
                )

            rejected = Subscription(
                "test_receiver",
                "1",
                self.subscription.event_types,
                self.subscription.scope_kinds,
                reject,
            )
            async with self.fixture() as engine, self.messaging() as transport:
                await publish_one(engine, transport, self.registry)
                await consume_one(engine, transport, rejected)
                await collect_one(engine, transport)
                async with engine.connect() as connection:
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT disposition FROM runtime.subscription_receipts")
                        ),
                        "rejected",
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.delivery_failures")
                        ),
                        1,
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM product.delivery_test_work")
                        ),
                        0,
                    )
                receipt = await accept(engine, rejected, await self.saved_notice(engine))
                self.assertEqual(receipt.disposition, "rejected")
                self.assertEqual(
                    (await transport.js.stream_info(transport.settings.failures)).state.messages, 0
                )

        asyncio.run(check())

    def test_max_delivery_advisory_is_persisted(self) -> None:
        """真实NATS耗尽5次投递后发通知；正式事件保留，失败可查询。"""

        async def check() -> None:
            async with self.fixture() as engine, self.messaging() as transport:
                await publish_one(engine, transport, self.registry)
                consumer = await transport.js.pull_subscribe_bind(
                    stream=transport.settings.stream, durable="test_receiver"
                )
                try:
                    for _ in range(5):
                        message = (await consumer.fetch(1, timeout=2))[0]
                        await message.nak()
                    with self.assertRaises(TimeoutError):
                        await consumer.fetch(1, timeout=1)
                finally:
                    await consumer.unsubscribe()
                self.assertTrue(await collect_one(engine, transport))
                async with engine.connect() as connection:
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT failure_kind FROM runtime.delivery_failures")
                        ),
                        "delivery_exhausted",
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.subscription_receipts")
                        ),
                        0,
                    )
                self.assertEqual(
                    (await transport.js.stream_info(transport.settings.stream)).state.messages, 1
                )
                notice = await self.saved_notice(engine)
                with self.assertRaises(PermissionError):
                    await redeliver(
                        engine, notice.handoff_id, operator="test", authorization="test-approval"
                    )
                maintenance = create_async_engine(self.migrator, poolclass=NullPool)
                try:
                    recovery = await redeliver(
                        maintenance,
                        notice.handoff_id,
                        operator="test",
                        authorization="test-approval",
                    )
                    self.assertEqual(
                        await redeliver(
                            maintenance,
                            notice.handoff_id,
                            operator="test",
                            authorization="test-approval",
                        ),
                        recovery,
                    )
                finally:
                    await maintenance.dispose()
                await publish_one(engine, transport, self.registry)
                await consume_one(engine, transport, self.subscription)
                self.assertEqual(self.calls, 1)

        asyncio.run(check())

    def test_late_subscriber_is_ignored(self) -> None:
        """晚加入者不扩大固定接收范围；忽略留痕且不执行承接函数。"""

        async def check() -> None:
            late = Subscription(
                "late_receiver",
                "1",
                self.subscription.event_types,
                self.subscription.scope_kinds,
                self.arrange_work,
            )
            async with self.fixture() as engine:
                receipt = await accept(engine, late, await self.saved_notice(engine))
                self.assertEqual(receipt.disposition, "ignored")
                self.assertEqual(self.calls, 0)

        asyncio.run(check())

    def test_receipt_and_work_are_atomic_and_deduplicated(self) -> None:
        """承接保存失败全部回滚；并发重复承接只创建一个工作。"""

        async def check() -> None:
            async with self.fixture() as engine:
                notice = await self.saved_notice(engine)

                async def failing(connection: AsyncConnection, event: EventNotice) -> Acceptance:
                    await self.arrange_work(connection, event)
                    raise RuntimeError("rollback")

                broken = Subscription(
                    "test_receiver",
                    "1",
                    self.subscription.event_types,
                    self.subscription.scope_kinds,
                    failing,
                )
                with self.assertRaisesRegex(RuntimeError, "rollback"):
                    await accept(engine, broken, notice)
                async with engine.connect() as connection:
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.subscription_receipts")
                        ),
                        0,
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM product.delivery_test_work")
                        ),
                        0,
                    )
                first, duplicate = await asyncio.gather(
                    accept(engine, self.subscription, notice),
                    accept(engine, self.subscription, notice),
                )
                self.assertEqual(first, duplicate)
                self.assertEqual(self.calls, 2)  # 一次已回滚、一次真正承接。
                forged = notice.model_copy(update={"scope_id": uuid4()})
                with self.assertRaises(PermissionError):
                    await accept(engine, self.subscription, forged)

        asyncio.run(check())

    def test_lease_recovery_and_attempt_budget(self) -> None:
        """进程丢失租约后可接手；旧持有者不能覆盖新尝试，预算不清零。"""

        async def check() -> None:
            async with self.fixture() as engine:
                first = await claim(engine, "first")
                assert first is not None
                self.assertIsNone(await claim(engine, "second"))
                with self.engine.begin() as connection:
                    connection.execute(
                        text(
                            "UPDATE runtime.handoffs SET "
                            "lease_until=clock_timestamp()-interval '1 second'"
                        )
                    )
                second = await claim(engine, "second")
                assert second is not None
                self.assertEqual(second.attempt_no, 2)
                await finish(engine, first, stream="wrong", sequence=1)
                async with engine.connect() as connection:
                    self.assertIsNone(
                        await connection.scalar(text("SELECT stream_name FROM runtime.handoffs"))
                    )
                await finish(engine, second, error_code="TEST_FAILURE")
                with self.engine.begin() as connection:
                    connection.execute(
                        text(
                            "UPDATE runtime.handoff_attempts SET "
                            "started_at=clock_timestamp()-interval '91 seconds'"
                        )
                    )
                    connection.execute(
                        text("UPDATE runtime.handoffs SET next_attempt_at=clock_timestamp()")
                    )
                self.assertIsNone(await claim(engine, "third"))
                async with engine.connect() as connection:
                    self.assertEqual(
                        await connection.scalar(text("SELECT state FROM runtime.handoffs")),
                        "exhausted",
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.delivery_failures")
                        ),
                        1,
                    )

        asyncio.run(check())

    def test_puback_loss_duplicate_delivery_and_ack_loss(self) -> None:
        """真实队列发布确认丢失后重发；收据已提交但未Ack时不重复创建工作。"""

        async def check() -> None:
            async with self.fixture() as engine, self.messaging() as transport:
                publish = transport.publish

                async def lose_ack(notice: EventNotice) -> tuple[str, int]:
                    await publish(notice)
                    raise TimeoutError("lost puback")

                with patch.object(transport, "publish", lose_ack):
                    await publish_one(engine, transport, self.registry)
                with self.engine.begin() as connection:
                    connection.execute(
                        text("UPDATE runtime.handoffs SET next_attempt_at=clock_timestamp()")
                    )
                await publish_one(engine, transport, self.registry)
                info = await transport.js.stream_info(transport.settings.stream)
                self.assertEqual(info.state.messages, 1)
                consumer = await transport.js.pull_subscribe_bind(
                    stream=transport.settings.stream, durable="test_receiver"
                )
                try:
                    message = (await consumer.fetch(1, timeout=2))[0]
                    await accept(
                        engine, self.subscription, DeliveryNotice.model_validate_json(message.data)
                    )
                    # 模拟承接后中断：队列重投，数据库收据仍存在。
                    await message.nak()
                finally:
                    await consumer.unsubscribe()
                await consume_one(engine, transport, self.subscription)
                self.assertEqual(self.calls, 1)
                self.assertEqual(
                    (await transport.js.stream_info(transport.settings.stream)).state.messages, 0
                )

        asyncio.run(check())

    def test_missing_consumer_and_missing_transport_are_visible(self) -> None:
        """订阅未就绪不发送；已发布却无人承接的丢失不能当作业务完成。"""

        async def check() -> None:
            async with self.fixture() as engine, self.messaging() as transport:
                await transport.js.delete_consumer(transport.settings.stream, "test_receiver")
                await publish_one(engine, transport, self.registry)
                self.assertEqual(
                    (await transport.js.stream_info(transport.settings.stream)).state.messages, 0
                )
                await transport.initialize(self.registry)
                with self.engine.begin() as connection:
                    connection.execute(
                        text("UPDATE runtime.handoffs SET next_attempt_at=clock_timestamp()")
                    )
                await publish_one(engine, transport, self.registry)
                await transport.js.delete_consumer(transport.settings.stream, "test_receiver")
                with self.engine.begin() as connection:
                    connection.execute(
                        text(
                            "UPDATE runtime.handoffs SET "
                            "created_at=clock_timestamp()-interval '151 seconds'"
                        )
                    )
                await reconcile(engine, transport)
                async with engine.connect() as connection:
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.subscription_receipts")
                        ),
                        0,
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.delivery_failures")
                        ),
                        1,
                    )

        asyncio.run(check())

    def test_reconciliation_does_not_depend_on_advisories(self) -> None:
        """模拟队列副本丢失而无失败通知，以正式收据缺失发现交接断层。"""

        async def check() -> None:
            async with self.fixture() as engine, self.messaging() as transport:
                await publish_one(engine, transport, self.registry)
                consumer = await transport.js.pull_subscribe_bind(
                    stream=transport.settings.stream, durable="test_receiver"
                )
                try:
                    message = (await consumer.fetch(1, timeout=2))[0]
                    await message.ack_sync(timeout=2)
                finally:
                    await consumer.unsubscribe()
                with self.engine.begin() as connection:
                    connection.execute(
                        text(
                            "UPDATE runtime.handoff_attempts SET "
                            "finished_at=clock_timestamp()-interval '151 seconds'"
                        )
                    )
                await reconcile(engine, transport)
                await reconcile(engine, transport)
                async with engine.connect() as connection:
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT failure_kind FROM runtime.delivery_failures")
                        ),
                        "transport_lost",
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.delivery_failures")
                        ),
                        1,
                    )

        asyncio.run(check())
