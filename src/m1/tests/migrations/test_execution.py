"""真实PG中的工作恢复合同；每例独立库，不创建正式学生或真实AI工作。"""

import asyncio
import json
import multiprocessing
import os
import unittest
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from multiprocessing.process import BaseProcess
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from deermind.bootstrap.executions import limits
from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.system.events.contracts import Ref
from deermind.foundation.system.executions import commands, dispatch, steps, store
from deermind.foundation.system.executions.contracts import (
    Authorization,
    Caller,
    Entry,
    Execution,
    Registry,
    RunInput,
    State,
)
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.temporal.executions import Transport
from deermind.infrastructure.temporal.relay import dispatch_one, reconcile
from execution_worker import child, lock_owner
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.service import RPCError, RPCStatusCode
from test_database import DatabaseTestCase


class ExecutionTests(DatabaseTestCase):
    """所有者测试适配只写隔离库，模拟真实业务事务与额度检查。"""

    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)
        self.scope = uuid4()
        self.queue = "e0113-test-" + uuid4().hex
        self.exhausted = False
        self.fail_finalize = False
        self.caller = Caller(
            Ref(owner="runtime", type="operator", id="test"),
            "product",
            frozenset({("material_import", self.scope)}),
            frozenset({"accept", "read", "retry", "cancel"}),
        )
        self.registry = Registry(
            [
                Entry(
                    "product",
                    "product.test_work",
                    "handler",
                    Ref(owner="product", type="implementation", id="test-work", revision=1),
                    "product.test_work",
                    self.queue,
                    lock_owner,
                    self.check_owner,
                    self.finalize_owner,
                )
            ]
        )
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE product.execution_effect (id uuid PRIMARY KEY)"))
            connection.execute(
                text("GRANT SELECT,INSERT ON product.execution_effect TO deermind_app")
            )
            connection.execute(
                text("CREATE TABLE product.execution_control (failure boolean, hold boolean)")
            )
            connection.execute(text("INSERT INTO product.execution_control VALUES (false,false)"))
            connection.execute(text("GRANT SELECT ON product.execution_control TO deermind_app"))

    @asynccontextmanager
    async def worker(self) -> AsyncGenerator[BaseProcess]:
        """真正的独立Worker进程；退出只终止本例进程，不重启正式Worker。"""
        process = multiprocessing.get_context("spawn").Process(
            target=child, args=(self.app.database, self.scope, self.queue)
        )
        process.start()
        try:
            yield process
        finally:
            if process.is_alive():
                process.terminate()
            await asyncio.to_thread(process.join, 10)
            if process.is_alive():
                process.kill()
                await asyncio.to_thread(process.join, 5)

    def tearDown(self) -> None:
        """只结束本例数据库登记的测试工作；失败用例也不遗留无人接手的执行。"""
        with self.engine.connect() as connection:
            identities = connection.scalars(
                text("SELECT workflow_id FROM runtime.execution_attempts")
            ).all()

        async def stop_test_work() -> None:
            transport = await self.transport()
            for identity in identities:
                handle = transport.client.get_workflow_handle(identity)
                try:
                    description = await handle.describe(rpc_timeout=timedelta(seconds=5))
                    if description.status == WorkflowExecutionStatus.RUNNING:
                        await handle.terminate(
                            "isolated test cleanup", rpc_timeout=timedelta(seconds=5)
                        )
                except RPCError as error:
                    if error.status != RPCStatusCode.NOT_FOUND:
                        raise

        try:
            if identities and os.environ.get("M1_TEST_TEMPORAL_ADDRESS"):
                asyncio.run(stop_test_work())
        finally:
            super().tearDown()

    async def transport(self) -> Transport:
        client = await Client.connect(
            os.environ["M1_TEST_TEMPORAL_ADDRESS"],
            namespace=os.environ["M1_TEST_TEMPORAL_NAMESPACE"],
        )
        return Transport(client, limits())

    async def wait_value(self, engine: AsyncEngine, query: str, expected: object) -> None:
        """有限等待数据库可观察效果；失败显示最后读到的值。"""
        actual = None
        for _ in range(300):
            async with engine.connect() as connection:
                actual = await connection.scalar(text(query))
            if actual == expected:
                return
            await asyncio.sleep(0.2)
        self.fail(f"Expected {expected!r}, last observed {actual!r}")

    def control(self, *, failure: bool = False, hold: bool = False) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text("UPDATE product.execution_control SET failure=:f,hold=:h"),
                {"f": failure, "h": hold},
            )

    @unittest.skipUnless(os.environ.get("M1_TEST_TEMPORAL_ADDRESS"), "Explicit Temporal required")
    def test_lost_start_receipt_reuses_workflow(self) -> None:
        """Temporal已经启动但本地未写回执；租约接手后仍是原Workflow、一个业务效果。"""

        async def check() -> None:
            async with self.fixture() as engine, self.worker():
                self.control(hold=True)
                async with engine.begin() as connection:
                    await self.accept(connection)
                transport = await self.transport()
                lease = await dispatch.claim(engine, limits())
                assert lease is not None
                original = await transport.start(lease.command)
                await self.wait_value(engine, "SELECT count(*) FROM runtime.step_results", 1)
                with self.engine.begin() as connection:
                    connection.execute(
                        text(
                            "UPDATE runtime.handoffs SET "
                            "lease_until=clock_timestamp()-interval '1 second'"
                        )
                    )
                self.assertTrue(await dispatch_one(engine, self.registry, transport))
                self.assertFalse(
                    await dispatch.finish(engine, lease, success=True, run_id=original)
                )
                self.control()
                await self.wait_value(engine, "SELECT state FROM runtime.executions", "completed")
                async with engine.connect() as connection:
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT temporal_run_id FROM runtime.execution_attempts")
                        ),
                        original,
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.handoff_attempts")
                        ),
                        2,
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM product.execution_effect")
                        ),
                        1,
                    )

        asyncio.run(check())

    @unittest.skipUnless(os.environ.get("M1_TEST_TEMPORAL_ADDRESS"), "Explicit Temporal required")
    def test_worker_kill_resumes_without_repeating_step(self) -> None:
        """已保存Step后强杀进程；新Worker接手剩余Activity，业务写入仍只有一次。"""

        async def check() -> None:
            async with self.fixture() as engine:
                self.control(hold=True)
                async with engine.begin() as connection:
                    await self.accept(connection)
                transport = await self.transport()
                async with self.worker() as process:
                    await dispatch_one(engine, self.registry, transport)
                    await self.wait_value(engine, "SELECT count(*) FROM runtime.step_results", 1)
                    process.kill()
                    await asyncio.to_thread(process.join, 5)
                self.control()
                async with self.worker():
                    await self.wait_value(
                        engine, "SELECT state FROM runtime.executions", "completed"
                    )
                async with engine.connect() as connection:
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM product.execution_effect")
                        ),
                        1,
                    )

        asyncio.run(check())

    @unittest.skipUnless(os.environ.get("M1_TEST_TEMPORAL_ADDRESS"), "Explicit Temporal required")
    def test_temporal_failure_recovery_and_stop(self) -> None:
        """重试耗尽后明确失败；授权恢复只补剩余步骤，随后停止阻止迟到完成。"""

        async def check() -> None:
            async with self.fixture() as engine, self.worker():
                self.control(failure=True)
                async with engine.begin() as connection:
                    execution = await self.accept(connection)
                transport = await self.transport()
                await dispatch_one(engine, self.registry, transport)
                await self.wait_value(engine, "SELECT state FROM runtime.executions", "failed")
                self.control(hold=True)
                async with engine.begin() as connection:
                    await commands.retry(
                        connection,
                        self.registry,
                        self.caller,
                        execution.execution_id,
                        request_id="recover",
                        seconds=300,
                    )
                await dispatch_one(engine, self.registry, transport)
                await self.wait_value(engine, "SELECT state FROM runtime.executions", "running")
                async with engine.begin() as connection:
                    await commands.cancel(
                        connection,
                        self.registry,
                        self.caller,
                        execution.execution_id,
                        request_id="stop-request",
                    )
                await dispatch_one(engine, self.registry, transport)
                self.control()
                await asyncio.sleep(1)
                async with engine.connect() as connection:
                    saved = await store.load(connection, execution.execution_id)
                    self.assertEqual(saved.state, "cancelled")
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM product.execution_effect")
                        ),
                        1,
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.execution_attempts")
                        ),
                        2,
                    )

        asyncio.run(check())

    @unittest.skipUnless(os.environ.get("M1_TEST_TEMPORAL_ADDRESS"), "Explicit Temporal required")
    def test_reconcile_closed_workflow_without_result(self) -> None:
        """外部终止已启动工作，核对负责失败收尾，不能伪造完成结果。"""

        async def check() -> None:
            async with self.fixture() as engine:
                async with engine.begin() as connection:
                    await self.accept(connection)
                transport = await self.transport()
                await dispatch_one(engine, self.registry, transport)
                async with engine.connect() as connection:
                    workflow_id = await connection.scalar(
                        text("SELECT workflow_id FROM runtime.execution_attempts")
                    )
                await transport.client.get_workflow_handle(workflow_id).terminate(
                    "isolated E01-13 test"
                )
                await reconcile(engine, self.registry, transport)
                await self.wait_value(engine, "SELECT state FROM runtime.executions", "failed")

        asyncio.run(check())

    @unittest.skipUnless(os.environ.get("M1_TEST_TEMPORAL_ADDRESS"), "Explicit Temporal required")
    def test_unreachable_temporal_does_not_fail_work(self) -> None:
        """模拟查询服务失联；故障日志不等于工作失败，已受理工作保持不变。"""

        async def check() -> None:
            async with self.fixture() as engine:
                async with engine.begin() as connection:
                    await self.accept(connection)
                transport = await self.transport()
                with (
                    patch.object(transport.client, "get_workflow_handle") as handle,
                    self.assertLogs("runtime", level="ERROR"),
                ):
                    handle.return_value.describe = AsyncMock(side_effect=ConnectionError())
                    await reconcile(engine, self.registry, transport)
                async with engine.connect() as connection:
                    self.assertEqual(
                        await connection.scalar(text("SELECT state FROM runtime.executions")),
                        "ready",
                    )

        asyncio.run(check())

    async def check_owner(
        self,
        connection: AsyncConnection,
        execution: Execution,
        authorization: Authorization,
        action: str,
    ) -> None:
        if authorization.resource_scope != {"kind": "material_import", "id": str(self.scope)}:
            raise PermissionError("Wrong resource")
        if action == "retry" and self.exhausted:
            raise ValueError("Original work budget is exhausted")

    async def finalize_owner(
        self,
        connection: AsyncConnection,
        execution: Execution,
        state: State,
        result: Ref | None,
    ) -> None:
        if self.fail_finalize:
            raise RuntimeError("Owner finalization failed")

    @asynccontextmanager
    async def fixture(self) -> AsyncGenerator[AsyncEngine]:
        engine = application_engine(self.app)
        try:
            yield engine
        finally:
            await engine.dispose()

    async def accept(self, connection: AsyncConnection, *, input_id: str = "fixed") -> Execution:
        return await store.accept(
            connection,
            self.registry,
            self.caller,
            entry_name="product.test_work",
            scope_kind="material_import",
            scope_id=self.scope,
            acceptance_key="request-1",
            input_ref=Ref(owner="product", type="input", id=input_id),
            seconds=300,
            basis_refs=[self.caller.actor],
        )

    async def run_input(self, connection: AsyncConnection, execution: Execution) -> RunInput:
        assert execution.active_attempt_id is not None
        current = await store.attempt(connection, execution.active_attempt_id)
        return RunInput(
            execution_id=execution.execution_id,
            attempt_id=current.attempt_id,
            input_ref=execution.input_ref,
            implementation_ref=execution.implementation_ref,
            ai_config_ref=execution.ai_config_ref,
            deadline_at=current.deadline_at,
        )

    async def effect(self, connection: AsyncConnection) -> tuple[Ref, Ref | None]:
        identity = uuid4()
        await connection.execute(
            text("INSERT INTO product.execution_effect VALUES (:id)"), {"id": identity}
        )
        result = Ref(owner="product", type="test_result", id=str(identity))
        return result, result

    def test_acceptance_atomic_and_idempotent(self) -> None:
        """回滚不留工作、事件或启动安排；相同请求只创建一次，异输入拒绝。"""

        async def check() -> None:
            async with self.fixture() as engine:
                with self.assertRaisesRegex(RuntimeError, "rollback"):
                    async with engine.begin() as connection:
                        await self.accept(connection)
                        raise RuntimeError("rollback")
                async with engine.begin() as connection:
                    for table in ("executions", "execution_attempts", "handoffs", "events"):
                        self.assertEqual(
                            await connection.scalar(text(f"SELECT count(*) FROM runtime.{table}")),
                            0,
                        )
                    first = await self.accept(connection)
                async with engine.begin() as connection:
                    second = await self.accept(connection)
                    self.assertEqual(first.execution_id, second.execution_id)
                    self.assertEqual(
                        await connection.scalar(text("SELECT count(*) FROM runtime.handoffs")), 1
                    )
                with self.assertRaisesRegex(ValueError, "identity conflict"):
                    async with engine.begin() as connection:
                        await self.accept(connection, input_id="changed")

        asyncio.run(check())

    def test_step_reused_and_old_attempt_rejected(self) -> None:
        """新尝试复用原Step；旧尝试迟到和同键异输入均不能增加业务效果。"""

        async def check() -> None:
            async with self.fixture() as engine:
                async with engine.begin() as connection:
                    execution = await self.accept(connection)
                    old = await self.run_input(connection, execution)
                    saved = await steps.save(
                        connection,
                        self.registry,
                        old,
                        name="save",
                        occurrence="1",
                        digest=steps.input_hash({"x": 1}),
                        commit=self.effect,
                    )
                    await commands.fail(connection, self.registry, old, self.caller.actor)
                async with engine.begin() as connection:
                    restored = await commands.retry(
                        connection,
                        self.registry,
                        self.caller,
                        execution.execution_id,
                        request_id="recovery",
                        seconds=300,
                    )
                    current = await self.run_input(connection, restored)
                    repeated = await steps.save(
                        connection,
                        self.registry,
                        current,
                        name="save",
                        occurrence="1",
                        digest=steps.input_hash({"x": 1}),
                        commit=self.effect,
                    )
                    self.assertEqual(saved, repeated)
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM product.execution_effect")
                        ),
                        1,
                    )
                for run, digest, message in (
                    (old, steps.input_hash({"x": 1}), "stale"),
                    (current, steps.input_hash({"x": 2}), "input conflict"),
                ):
                    with self.assertRaisesRegex(ValueError, message):
                        async with engine.begin() as connection:
                            await steps.save(
                                connection,
                                self.registry,
                                run,
                                name="save",
                                occurrence="1",
                                digest=digest,
                                commit=self.effect,
                            )

        asyncio.run(check())

    def test_stop_prevents_late_commit_and_restart(self) -> None:
        """停止先落定资格；迟到完成不能保存，原请求重发也不重新启动。"""

        async def check() -> None:
            async with self.fixture() as engine:
                async with engine.begin() as connection:
                    execution = await self.accept(connection)
                    run = await self.run_input(connection, execution)
                    cancelled = await commands.cancel(
                        connection,
                        self.registry,
                        self.caller,
                        execution.execution_id,
                        request_id="stop-request",
                    )
                    self.assertEqual(cancelled.state, "cancelled")
                    self.assertEqual(
                        await connection.scalar(
                            text(
                                "SELECT source_request_id FROM runtime.events "
                                "WHERE payload->>'outcome'='stopped'"
                            )
                        ),
                        "stop-request",
                    )
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT logical_key FROM runtime.handoffs WHERE kind='cancel'")
                        ),
                        f"stop-request:{run.attempt_id}",
                    )
                with self.assertRaisesRegex(ValueError, "stale"):
                    async with engine.begin() as connection:
                        await commands.complete(connection, self.registry, run, self.caller.actor)
                with self.assertRaisesRegex(ValueError, "Only failed"):
                    async with engine.begin() as connection:
                        await commands.retry(
                            connection,
                            self.registry,
                            self.caller,
                            execution.execution_id,
                            request_id="retry-stopped",
                            seconds=300,
                        )
                async with engine.begin() as connection:
                    self.assertEqual((await self.accept(connection)).state, "cancelled")
                    self.assertEqual(
                        await connection.scalar(
                            text("SELECT count(*) FROM runtime.execution_attempts")
                        ),
                        1,
                    )

        asyncio.run(check())

    def test_failed_owner_rolls_back_completion(self) -> None:
        """所有者收尾失败不能出现底座已完成；重试完成只记一份完成事实。"""

        async def check() -> None:
            async with self.fixture() as engine:
                async with engine.begin() as connection:
                    execution = await self.accept(connection)
                    run = await self.run_input(connection, execution)
                self.fail_finalize = True
                with self.assertRaisesRegex(RuntimeError, "finalization"):
                    async with engine.begin() as connection:
                        await commands.complete(connection, self.registry, run, self.caller.actor)
                self.fail_finalize = False
                async with engine.begin() as connection:
                    self.assertEqual(
                        (await store.load(connection, execution.execution_id)).state, "ready"
                    )
                    await commands.complete(connection, self.registry, run, self.caller.actor)
                    await commands.complete(connection, self.registry, run, self.caller.actor)
                    self.assertEqual(
                        await connection.scalar(
                            text(
                                "SELECT count(*) FROM runtime.events "
                                "WHERE payload->>'outcome'='completed'"
                            )
                        ),
                        1,
                    )

        asyncio.run(check())

    def test_recovery_preserves_budget_and_deadline(self) -> None:
        """原工作额度不因恢复清零；重复恢复命令不能给当前尝试续时。"""

        async def check() -> None:
            async with self.fixture() as engine:
                async with engine.begin() as connection:
                    execution = await self.accept(connection)
                    run = await self.run_input(connection, execution)
                    await commands.fail(connection, self.registry, run, self.caller.actor)
                self.exhausted = True
                with self.assertRaisesRegex(ValueError, "budget"):
                    async with engine.begin() as connection:
                        await commands.retry(
                            connection,
                            self.registry,
                            self.caller,
                            execution.execution_id,
                            request_id="retry",
                            seconds=300,
                        )
                self.exhausted = False
                async with engine.begin() as connection:
                    saved = await commands.retry(
                        connection,
                        self.registry,
                        self.caller,
                        execution.execution_id,
                        request_id="retry",
                        seconds=300,
                    )
                    first = await self.run_input(connection, saved)
                    again = await commands.retry(
                        connection,
                        self.registry,
                        self.caller,
                        execution.execution_id,
                        request_id="retry",
                        seconds=900,
                    )
                    self.assertEqual(first, await self.run_input(connection, again))
                    self.assertEqual(saved.input_ref, execution.input_ref)

        asyncio.run(check())

    def test_read_requires_scope_and_fact_records_are_complete(self) -> None:
        """其他资源的调用方不可读取；控制事实保存完整DTO，不依赖当前工作行。"""

        async def check() -> None:
            async with self.fixture() as engine:
                async with engine.begin() as connection:
                    execution = await self.accept(connection)
                other = Caller(self.caller.actor, "product", frozenset(), frozenset({"read"}))
                with self.assertRaises(PermissionError):
                    async with engine.connect() as connection:
                        await commands.read(
                            connection, self.registry, other, execution.execution_id
                        )
                async with engine.connect() as connection:
                    body = await connection.scalar(text("SELECT payload FROM runtime.events"))
                    records = {
                        item["record_type"]: item["content"]["value"] for item in body["records"]
                    }
                    fact = Execution.model_validate_json(json.dumps(records["runtime.executions"]))
                    self.assertEqual(fact.execution_id, execution.execution_id)
                    self.assertIn("runtime.execution_attempts", records)

        asyncio.run(check())
