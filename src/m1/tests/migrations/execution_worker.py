"""隔离Temporal用例的所有者适配和子进程Worker；不进入正式业务注册。"""

import asyncio
import os
from datetime import timedelta
from typing import TypedDict
from uuid import UUID, uuid4

from deermind.bootstrap.executions import limits
from deermind.foundation.system.events.contracts import Ref
from deermind.foundation.system.executions import steps
from deermind.foundation.system.executions.contracts import (
    Authorization,
    Entry,
    Execution,
    Registry,
    RunInput,
    State,
)
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.temporal.executions import Lifecycle
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError
from temporalio.worker import Worker


def registry(scope: UUID, queue: str) -> Registry:
    async def check(
        connection: AsyncConnection,
        execution: Execution,
        authorization: Authorization,
        action: str,
    ) -> None:
        if execution.scope_id != scope:
            raise PermissionError("Invalid test scope")

    async def finalize(
        connection: AsyncConnection,
        execution: Execution,
        state: State,
        result: Ref | None,
    ) -> None:
        """测试所有者无额外终态；业务效果由已保存Step计数。"""

    return Registry(
        [
            Entry(
                "product",
                "product.test_work",
                "handler",
                Ref(owner="product", type="implementation", id="test-work", revision=1),
                "product.test_work",
                queue,
                lock_owner,
                check,
                finalize,
            )
        ]
    )


async def lock_owner(connection: AsyncConnection, kind: str, identity: UUID) -> None:
    """测试业务锁；生产模块在相同位置锁定自己的空间或教材记录。"""
    await connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"test-owner:{kind}:{identity}"},
    )


class ActivityOptions(TypedDict):
    start_to_close_timeout: timedelta
    schedule_to_close_timeout: timedelta
    retry_policy: RetryPolicy


@workflow.defn(name="product.test_work", sandboxed=False)
class TestWorkflow:
    """测试Workflow仅编排Activity；关闭沙箱只避免动态临时测试模块的装载差异。"""

    @workflow.run
    async def run(self, body: str) -> str:
        options = ActivityOptions(
            start_to_close_timeout=timedelta(seconds=15),
            # 包含子进程启动和Temporal故障接手时间；不修改正式任务预算。
            schedule_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=2),
        )
        try:
            await workflow.execute_activity("runtime.execution_started", body, **options)
            result = await workflow.execute_activity(
                "test.save_step", body, result_type=str, **options
            )
            await workflow.execute_activity(
                "test.gate", body, heartbeat_timeout=timedelta(seconds=2), **options
            )
            await workflow.execute_activity(
                "runtime.execution_completed", args=[body, result], **options
            )
            return result
        except ActivityError:
            await workflow.execute_activity(
                "runtime.execution_failed", args=[body, "TEST_FAILURE"], **options
            )
            raise ApplicationError("Test workflow failed") from None


class TestActivities:
    def __init__(self, engine: AsyncEngine, entries: Registry) -> None:
        self.engine = engine
        self.entries = entries

    @activity.defn(name="test.save_step")
    async def save_step(self, body: str) -> str:
        run = RunInput.model_validate_json(body)

        async def commit(connection: AsyncConnection) -> tuple[Ref, Ref | None]:
            identity = uuid4()
            await connection.execute(
                text("INSERT INTO product.execution_effect VALUES (:id)"), {"id": identity}
            )
            result = Ref(owner="product", type="test_result", id=str(identity))
            return result, result

        async with self.engine.begin() as connection:
            result = await steps.save(
                connection,
                self.entries,
                run,
                name="save",
                occurrence="1",
                digest=steps.input_hash({"value": 1}),
                commit=commit,
            )
            return result.output_ref.model_dump_json()

    @activity.defn(name="test.gate")
    async def gate(self, body: str) -> None:
        """用测试表模拟临时故障与长I/O，便于在确定位置中断Worker。"""
        while True:
            async with self.engine.connect() as connection:
                failure, hold = (
                    await connection.execute(
                        text("SELECT failure,hold FROM product.execution_control")
                    )
                ).one()
            if failure:
                raise ApplicationError("Deliberate retryable test failure")
            if not hold:
                return
            activity.heartbeat()
            await asyncio.sleep(0.2)


async def serve(database: str, scope: UUID, queue: str) -> None:
    """子进程自行建连接；凭据从测试环境读取，不放命令行或日志。"""
    url = URL.create(
        "postgresql+psycopg",
        username="deermind_app",
        password=os.environ["M1_TEST_APP_PASSWORD"],
        host=os.environ["M1_DB_HOST"],
        port=int(os.environ["M1_DB_PORT"]),
        database=database,
    )
    engine = application_engine(url)
    client = await Client.connect(
        os.environ["M1_TEST_TEMPORAL_ADDRESS"], namespace=os.environ["M1_TEST_TEMPORAL_NAMESPACE"]
    )
    entries = registry(scope, queue)
    lifecycle = Lifecycle(engine, entries, limits())
    actions = TestActivities(engine, entries)
    try:
        async with Worker(
            client,
            task_queue=queue,
            workflows=[TestWorkflow],
            activities=[
                lifecycle.started,
                lifecycle.completed,
                lifecycle.failed,
                actions.save_step,
                actions.gate,
            ],
        ):
            await asyncio.Event().wait()
    finally:
        await engine.dispose()


def child(database: str, scope: UUID, queue: str) -> None:
    """由显式隔离测试启动，可被SIGKILL；生产Worker不导入此文件。"""
    asyncio.run(serve(database, scope, queue))
