"""E01-14真实PG/Temporal合同测试：先查结果、一次接续、恢复不续期。"""

import asyncio
import os
import unittest
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import uuid4

from deermind.bootstrap.executions import limits
from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.system.delivery.contracts import EventNotice
from deermind.foundation.system.executions import commands, store
from deermind.foundation.system.executions.contracts import RunInput
from deermind.foundation.system.waits import facts, notifications
from deermind.foundation.system.waits.contracts import Wait
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.temporal.executions import Lifecycle, Transport
from deermind.infrastructure.temporal.relay import dispatch_one
from deermind.infrastructure.temporal.waits import Activities, reconcile
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker
from test_database import DatabaseTestCase
from wait_fixture import Fixture, WaitingWorkflow


class FindWait:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    @activity.defn(name="test.find_wait")
    async def find(self, body: str) -> str:
        run = RunInput.model_validate_json(body)
        async with self.engine.connect() as connection:
            return str(
                await connection.scalar(
                    text("SELECT wait_id FROM runtime.waits WHERE execution_id=:id"),
                    {"id": run.execution_id},
                )
            )


class WaitTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)
        self.fixture = Fixture(uuid4(), "e0114-" + uuid4().hex)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE interaction.wait_effect "
                    "(id uuid PRIMARY KEY,resolution text NOT NULL)"
                )
            )
            connection.execute(
                text("GRANT SELECT,INSERT ON interaction.wait_effect TO deermind_app")
            )

    @asynccontextmanager
    async def database(self) -> AsyncGenerator[AsyncEngine]:
        engine = application_engine(self.app)
        try:
            yield engine
        finally:
            await engine.dispose()

    def expire(self, wait: Wait) -> None:
        """只在隔离库推进测试时钟条件，不改正式配置，减少用例等待。"""
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE runtime.waits SET created_at=clock_timestamp()-interval '2 seconds',"
                    "deadline_at=clock_timestamp()-interval '1 second' WHERE wait_id=:id"
                ),
                {"id": wait.wait_id},
            )

    def test_early_result_and_repeat_handling(self) -> None:
        async def check() -> None:
            f = self.fixture
            async with self.database() as engine:
                async with engine.begin() as connection:
                    producer, consumer, key = await f.setup(connection)
                    published = await f.publish(connection, producer, key)
                    wait = await f.register(connection, consumer, key)
                async with engine.begin() as connection:
                    resolved = await f.waits.probe(connection, consumer, wait.wait_id)
                    self.assertEqual(resolved.resolution, "matched")
                    self.assertEqual(resolved.matched_event_ref, published.event_id)
                    first = await f.waits.handle(connection, consumer, wait.wait_id)
                    again = await f.waits.handle(connection, consumer, wait.wait_id)
                    self.assertEqual(first, again)
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM interaction.wait_effect")
                        ),
                        1,
                    )

        asyncio.run(check())

    def test_deadline_queries_result_and_late_result_does_not_revive(self) -> None:
        async def check() -> None:
            f = self.fixture
            async with self.database() as engine:
                async with engine.begin() as connection:
                    producer, consumer, key = await f.setup(connection)
                    available = await f.register(connection, consumer, key, step="available")
                    late = await f.register(connection, consumer, key, step="late")
                self.expire(available)
                self.expire(late)
                async with engine.begin() as connection:
                    self.assertEqual(
                        (await f.waits.probe(connection, consumer, late.wait_id)).resolution,
                        "timed_out",
                    )
                    await f.waits.handle(connection, consumer, late.wait_id)
                async with engine.begin() as connection:
                    await f.publish(connection, producer, key)
                async with engine.begin() as connection:
                    self.assertEqual(
                        (await f.waits.probe(connection, consumer, available.wait_id)).resolution,
                        "matched",
                    )
                    self.assertEqual(
                        (await f.waits.probe(connection, consumer, late.wait_id)).resolution,
                        "timed_out",
                    )
                    self.assertEqual(
                        (await store.load(connection, producer.execution_id)).state, "ready"
                    )

        asyncio.run(check())

    def test_read_failure_is_not_timeout_and_failed_handler_rolls_back(self) -> None:
        async def check() -> None:
            f = self.fixture
            async with self.database() as engine:
                async with engine.begin() as connection:
                    producer, consumer, key = await f.setup(connection)
                    wait = await f.register(connection, consumer, key)
                self.expire(wait)
                f.fail_probe = True
                with self.assertRaises(RuntimeError):
                    async with engine.begin() as connection:
                        await f.waits.probe(connection, consumer, wait.wait_id)
                f.fail_probe = False
                f.fail_handle = True
                async with engine.begin() as connection:
                    self.assertEqual(
                        (await facts.read_wait(connection, str(wait.wait_id))).resolution, "pending"
                    )
                    await f.publish(connection, producer, key)
                    await f.waits.probe(connection, consumer, wait.wait_id)
                    failed = await f.waits.handle(connection, consumer, wait.wait_id)
                    self.assertEqual(failed.state, "failed")
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM interaction.wait_effect")
                        ),
                        0,
                    )
                f.fail_handle = False
                async with engine.begin() as connection:
                    self.assertEqual(
                        (await f.waits.handle(connection, consumer, wait.wait_id)).state,
                        "committed",
                    )

        asyncio.run(check())

    def test_recovery_keeps_wait_deadline_and_result_identity(self) -> None:
        async def check() -> None:
            f = self.fixture
            async with self.database() as engine:
                async with engine.begin() as connection:
                    producer, consumer, key = await f.setup(connection)
                    wait = await f.register(connection, consumer, key)
                    for run in (producer, consumer):
                        await commands.fail(connection, f.entries, run, run.input_ref)
                    failed = await f.results.read(
                        connection, f.caller("interaction"), "learning_space", key
                    )
                    self.assertEqual(failed.state, "failed")
                    with self.assertRaisesRegex(ValueError, "continuation budget"):
                        async with connection.begin_nested():
                            short = await commands.retry(
                                connection,
                                f.entries,
                                f.caller("interaction"),
                                consumer.execution_id,
                                request_id="too-short",
                                seconds=5,
                            )
                            await f.register(connection, await f.run_input(connection, short), key)
                    resumed: list[RunInput] = []
                    for run, owner in ((producer, "product"), (consumer, "interaction")):
                        execution = await commands.retry(
                            connection,
                            f.entries,
                            f.caller(owner),
                            run.execution_id,
                            request_id="recover",
                            seconds=180,
                        )
                        resumed.append(await f.run_input(connection, execution))
                    again = await f.register(connection, resumed[1], key, seconds=100)
                    self.assertEqual(again.deadline_at, wait.deadline_at)
                    await f.publish(connection, resumed[0], key)
                    self.assertEqual(
                        (await f.waits.probe(connection, resumed[1], wait.wait_id)).resolution,
                        "matched",
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.result_attempts")
                        ),
                        2,
                    )
                with self.assertRaises(ValueError):
                    async with engine.begin() as connection:
                        await f.waits.handle(connection, consumer, wait.wait_id)

        asyncio.run(check())

    def test_cancel_and_duplicate_notifications(self) -> None:
        async def check() -> None:
            f = self.fixture
            async with self.database() as engine:
                async with engine.begin() as connection:
                    producer, consumer, key = await f.setup(connection)
                    wait = await f.register(connection, consumer, key)
                    published = await f.publish(connection, producer, key)
                    subscriber = notifications.subscription(f.entries, f.policies)
                    assert subscriber is not None
                    notice = EventNotice(
                        delivery_id=uuid4(),
                        handoff_id=uuid4(),
                        event_id=published.event_id,
                        event_type="TestResultPublished",
                        schema_version=1,
                        producer="product",
                        scope_kind="learning_space",
                        scope_id=f.scope,
                    )
                    first = await subscriber.accept(connection, notice)
                    self.assertEqual(first, await subscriber.accept(connection, notice))
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.handoffs WHERE kind='signal'")
                        ),
                        1,
                    )
                    await f.waits.cancel(connection, f.caller("interaction"), wait.wait_id)
                    self.assertEqual(
                        (await f.waits.probe(connection, consumer, wait.wait_id)).resolution,
                        "cancelled",
                    )
                    self.assertEqual(
                        (await f.waits.handle(connection, consumer, wait.wait_id)).state,
                        "cancelled",
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM interaction.wait_effect")
                        ),
                        0,
                    )

        asyncio.run(check())

    def test_limits_ownership_and_immutable_publication(self) -> None:
        async def check() -> None:
            f = self.fixture
            async with self.database() as engine:
                async with engine.begin() as connection:
                    producer, consumer, key = await f.setup(connection)
                    published = await f.publish(connection, producer, key)
                for seconds in (0, 301, 179):
                    with self.assertRaises(ValueError):
                        async with engine.begin() as connection:
                            await f.register(connection, consumer, key, seconds=seconds)
                with self.assertRaises(PermissionError):
                    async with engine.connect() as connection:
                        await f.results.read(connection, f.caller("product"), "learning_space", key)
                with self.assertRaises(ValueError):
                    async with engine.begin() as connection:
                        await f.results.publish(
                            connection,
                            producer,
                            key,
                            result_ref=published.result_ref,
                            event_id=published.event_id,
                            payload={"value": "different"},
                            publication_refs=[],
                        )
                with self.assertRaises(DBAPIError):
                    async with engine.begin() as connection:
                        await connection.execute(text("DELETE FROM runtime.published_results"))
                async with engine.begin() as connection:
                    original = await f.results.publish(
                        connection,
                        producer,
                        key,
                        result_ref=published.result_ref,
                        event_id=published.event_id,
                        payload=published.payload,
                        publication_refs=[],
                    )
                    self.assertEqual(original, published)

        asyncio.run(check())

    def test_reconciliation_recovers_missing_notification(self) -> None:
        async def check() -> None:
            f = self.fixture
            async with self.database() as engine:
                async with engine.begin() as connection:
                    producer, consumer, key = await f.setup(connection)
                    wait = await f.register(connection, consumer, key)
                    await f.publish(connection, producer, key)
                await reconcile(engine, f.waits, timeout_seconds=30)
                await reconcile(engine, f.waits, timeout_seconds=30)
                async with engine.connect() as connection:
                    self.assertEqual(
                        (await facts.read_wait(connection, str(wait.wait_id))).resolution, "matched"
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.handoffs WHERE kind='signal'")
                        ),
                        1,
                    )

        asyncio.run(check())

    def test_cancelling_whole_work_preserves_producer(self) -> None:
        """整项停止要撤销未提交接续；不取消生产方，也不抹掉已命中的决定。"""

        async def check() -> None:
            f = self.fixture
            async with self.database() as engine:
                async with engine.begin() as connection:
                    producer, consumer, key = await f.setup(connection)
                    pending = await f.register(connection, consumer, key, step="pending")
                    matched = await f.register(connection, consumer, key, step="matched")
                    await f.publish(connection, producer, key)
                    await f.waits.probe(connection, consumer, matched.wait_id)
                    await commands.cancel(
                        connection,
                        f.entries,
                        f.caller("interaction"),
                        consumer.execution_id,
                        request_id="stop",
                    )
                    self.assertEqual(
                        (await facts.read_wait(connection, str(pending.wait_id))).resolution,
                        "cancelled",
                    )
                    self.assertEqual(
                        (await facts.read_wait(connection, str(matched.wait_id))).resolution,
                        "matched",
                    )
                    self.assertEqual(
                        (await facts.read_handling(connection, matched)).state, "cancelled"
                    )
                    self.assertEqual(
                        (await store.load(connection, producer.execution_id)).state, "ready"
                    )
                with self.assertRaises(ValueError):
                    async with engine.begin() as connection:
                        await f.waits.handle(connection, consumer, matched.wait_id)

        asyncio.run(check())

    def test_concurrent_continuations_commit_once(self) -> None:
        """两个进程同时接续同一等待，业务写入和收据只提交一次。"""

        async def check() -> None:
            f = self.fixture
            async with self.database() as engine:
                async with engine.begin() as connection:
                    producer, consumer, key = await f.setup(connection)
                    wait = await f.register(connection, consumer, key)
                    await f.publish(connection, producer, key)
                    await f.waits.probe(connection, consumer, wait.wait_id)

                async def handle() -> str:
                    async with engine.begin() as connection:
                        return (
                            await f.waits.handle(connection, consumer, wait.wait_id)
                        ).model_dump_json()

                first, second = await asyncio.gather(handle(), handle())
                self.assertEqual(first, second)
                async with engine.connect() as connection:
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM interaction.wait_effect")
                        ),
                        1,
                    )

        asyncio.run(check())

    def test_probe_crossing_deadline_checks_again(self) -> None:
        """到期前的查询跨过截止点，不得用旧空结果覆盖已经提交的结果。"""

        async def check() -> None:
            f = self.fixture
            async with self.database() as engine:
                async with engine.begin() as connection:
                    producer, consumer, key = await f.setup(connection)
                    wait = await f.register(connection, consumer, key, seconds=0.3)
                f.probe_delay_once = 0.6

                async def publish_later() -> None:
                    await asyncio.sleep(0.1)
                    async with engine.begin() as connection:
                        await f.publish(connection, producer, key)

                async def probe() -> str:
                    async with engine.begin() as connection:
                        return (await f.waits.probe(connection, consumer, wait.wait_id)).resolution

                resolution, _ = await asyncio.gather(probe(), publish_later())
                self.assertEqual(resolution, "matched")

        asyncio.run(check())

    def test_publication_and_source_fact_rollback_together(self) -> None:
        async def check() -> None:
            f = self.fixture
            async with self.database() as engine:
                async with engine.begin() as connection:
                    producer, _, key = await f.setup(connection)
                with self.assertRaises(RuntimeError):
                    async with engine.begin() as connection:
                        await f.publish(connection, producer, key)
                        raise RuntimeError("Fail before commit")
                async with engine.connect() as connection:
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.published_results")
                        ),
                        0,
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text(
                                "SELECT count(*) FROM runtime.events "
                                "WHERE event_type='TestResultPublished'"
                            )
                        ),
                        0,
                    )
                    state = await f.results.read(
                        connection, f.caller("interaction"), "learning_space", key
                    )
                    self.assertEqual(state.state, "pending")

        asyncio.run(check())

    @unittest.skipUnless(os.environ.get("M1_TEST_TEMPORAL_ADDRESS"), "Explicit Temporal required")
    def test_temporal_wait_releases_activity_and_survives_worker_restart(self) -> None:
        async def check() -> None:
            f = self.fixture
            client = await Client.connect(
                os.environ["M1_TEST_TEMPORAL_ADDRESS"],
                namespace=os.environ["M1_TEST_TEMPORAL_NAMESPACE"],
            )
            async with self.database() as engine:
                async with engine.begin() as connection:
                    producer, consumer, key = await f.setup(connection)
                    wait = await f.register(connection, consumer, key, seconds=60)
                    attempt = await store.attempt(connection, consumer.attempt_id)
                    # 本例只运行消费者；生产者由测试端独立提交结果。
                    await connection.execute(
                        text("UPDATE runtime.handoffs SET state='delivered' WHERE logical_key=:id"),
                        {"id": str(producer.attempt_id)},
                    )
                lifecycle = Lifecycle(engine, f.entries, limits())
                actions = Activities(engine, f.waits, timeout_seconds=30)
                finder = FindWait(engine)

                def worker() -> Worker:
                    return Worker(
                        client,
                        task_queue=f.queue,
                        workflows=[WaitingWorkflow],
                        activities=[
                            finder.find,
                            actions.probe,
                            actions.handle,
                            lifecycle.completed,
                        ],
                        max_concurrent_activities=1,
                    )

                transport = Transport(client, limits())
                handle = client.get_workflow_handle(attempt.workflow_id)
                try:
                    async with worker():
                        await dispatch_one(engine, f.entries, transport)
                        # 有限观察原生Timer；如果等待占住Activity槽，后续探测无法运行。
                        for _ in range(100):
                            history = await handle.fetch_history()
                            if any(
                                event.HasField("timer_started_event_attributes")
                                for event in history.events
                            ):
                                break
                            await asyncio.sleep(0.1)
                        else:
                            self.fail("Wait never released into a Temporal timer")
                    async with engine.begin() as connection:
                        await f.publish(connection, producer, key)
                    await reconcile(engine, f.waits, timeout_seconds=30)
                    async with worker():
                        await dispatch_one(engine, f.entries, transport)
                        self.assertEqual(await asyncio.wait_for(handle.result(), 30), "committed")
                    async with engine.connect() as connection:
                        self.assertEqual(
                            (await facts.read_wait(connection, str(wait.wait_id))).resolution,
                            "matched",
                        )
                        self.assertEqual(
                            await connection.scalar(
                                text("SELECT count(*) FROM interaction.wait_effect")
                            ),
                            1,
                        )
                finally:
                    description = await handle.describe()
                    if description.status and description.status.name == "RUNNING":
                        await handle.terminate("isolated test cleanup")

        asyncio.run(check())
