"""E01-18 隔离 Worker，验证持久步骤和外置载荷跨进程恢复。"""

import asyncio
import hashlib
import multiprocessing
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from multiprocessing.process import BaseProcess
from pathlib import Path
from uuid import UUID, uuid4

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import RunInput
from deermind.bootstrap import runtime
from deermind.bootstrap.executions import limits
from deermind.bootstrap.settings import Settings
from deermind.bootstrap.temporal import connect_temporal
from deermind.foundation.system.executions import steps
from deermind.foundation.system.executions.contracts import Registry
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.files.payload_codec import ENCODING, INLINE_LIMIT, PayloadReference
from deermind.infrastructure.temporal.executions import Lifecycle
from execution_worker import ActivityOptions
from foundation_chain_data import (
    EXPECTED_SHA,
    PAYLOAD,
    WORKFLOW_NAME,
    publish_result,
    read_input,
    registry,
    result_ref,
)
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from temporalio import activity, workflow
from temporalio.api.enums.v1 import EventType
from temporalio.client import Client, WorkflowHistory
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError
from temporalio.worker import Worker

_PREPARE = "e0118.prepare"
_VERIFY = "e0118.verify"
_FINISH = "e0118.finish"
_RELEASE = "e0118.release_checkpoint"
_ACTIVITY_TIMEOUT = timedelta(seconds=25)
_ACTIVITY_BUDGET = timedelta(seconds=65)
_RPC_TIMEOUT = timedelta(seconds=8)
_RETRY = RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=2)
_SHA_KIND = "foundation_chain_sha256"


@workflow.defn(name=WORKFLOW_NAME, sandboxed=False)
class ChainWorkflow:
    """使用测试信号停在两步之间，生产 Worker 不登记此流程。"""

    def __init__(self) -> None:
        self.released = False

    @workflow.signal(name=_RELEASE)
    async def release_checkpoint(self) -> None:
        self.released = True

    @workflow.run
    async def run(self, body: str) -> str:
        options = ActivityOptions(
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            schedule_to_close_timeout=_ACTIVITY_BUDGET,
            retry_policy=_RETRY,
        )
        try:
            await workflow.execute_activity("runtime.execution_started", body, **options)
            payload = await workflow.execute_activity(_PREPARE, body, result_type=bytes, **options)
            await workflow.wait_condition(lambda: self.released)
            result = await workflow.execute_activity(
                _VERIFY, args=[body, payload], result_type=str, **options
            )
            await workflow.execute_activity(_FINISH, args=[body, result], **options)
            return result
        except ActivityError:
            await workflow.execute_activity(
                "runtime.execution_failed", args=[body, "E01_18_TEST_FAILURE"], **options
            )
            raise ApplicationError("E01-18 test workflow failed") from None


class ChainActivities:
    def __init__(
        self, engine: AsyncEngine, entries: Registry, lifecycle: Lifecycle, deployment: str
    ) -> None:
        self.engine = engine
        self.entries = entries
        self.lifecycle = lifecycle
        self.deployment = deployment

    @activity.defn(name=_PREPARE)
    async def prepare(self, body: str) -> bytes:
        """先提交第一步，再把大载荷作为 Temporal Activity 结果返回。"""
        run = RunInput.model_validate_json(body)
        source = await read_input(self.engine, run)
        digest = steps.input_hash({"event": run.input_ref.id, "text": source})

        async def commit(connection: AsyncConnection) -> tuple[Ref, Ref | None]:
            return Ref(owner="product", type=_SHA_KIND, id=EXPECTED_SHA), None

        async with self.engine.begin() as connection:
            await steps.save(
                connection,
                self.entries,
                run,
                name="prepare",
                occurrence="1",
                digest=digest,
                commit=commit,
            )
        return PAYLOAD

    @activity.defn(name=_VERIFY)
    async def verify(self, body: str, payload: bytes) -> str:
        """用恢复后实际收到的字节计算 SHA，并随固定第二步保存。"""
        run = RunInput.model_validate_json(body)
        observed = hashlib.sha256(payload).hexdigest()
        if observed != EXPECTED_SHA:
            raise ApplicationError("E01-18 payload SHA mismatch", non_retryable=True)

        async def commit(connection: AsyncConnection) -> tuple[Ref, Ref | None]:
            return Ref(owner="product", type=_SHA_KIND, id=observed), None

        async with self.engine.begin() as connection:
            await steps.save(
                connection,
                self.entries,
                run,
                name="verify",
                occurrence="1",
                digest=steps.input_hash({"source_event_id": run.input_ref.id, "sha256": observed}),
                commit=commit,
            )
        return result_ref(run.execution_id).model_dump_json()

    @activity.defn(name=_FINISH)
    async def finish(self, body: str, result: str) -> None:
        await self.lifecycle.completed(body, result)
        run = RunInput.model_validate_json(body)
        await publish_result(self.engine, run.execution_id, self.deployment)


async def _serve(
    database: URL, settings: Settings, scope: UUID, deployment: str, ready: Path
) -> None:
    engine = application_engine(database)
    entries = registry(scope, settings.task_queue)
    lifecycle = runtime.lifecycle(engine, entries, limits())
    actions = ChainActivities(engine, entries, lifecycle, deployment)
    try:
        client = await connect_temporal(settings, engine)
        async with Worker(
            client,
            task_queue=settings.task_queue,
            workflows=[ChainWorkflow],
            activities=[
                lifecycle.started,
                lifecycle.failed,
                actions.prepare,
                actions.verify,
                actions.finish,
            ],
        ):
            ready.touch()
            await asyncio.Future[None]()
    finally:
        await engine.dispose()


def _child(database: URL, settings: Settings, scope: UUID, deployment: str, ready: Path) -> None:
    asyncio.run(_serve(database, settings, scope, deployment, ready))


@asynccontextmanager
async def worker(
    database: URL, settings: Settings, scope: UUID, deployment: str
) -> AsyncGenerator[BaseProcess]:
    """执行与清理只影响本用例的子进程。"""
    ready = settings.files_root / f"chain-worker-ready-{uuid4().hex}"
    process = multiprocessing.get_context("spawn").Process(
        target=_child, args=(database, settings, scope, deployment, ready)
    )
    process.start()
    try:
        async with asyncio.timeout(60):
            while not ready.is_file():
                if not process.is_alive():
                    raise RuntimeError(f"Test Worker exited with status {process.exitcode}")
                await asyncio.sleep(0.1)
        yield process
    finally:
        if process.is_alive():
            process.terminate()
        await asyncio.to_thread(process.join, 8)
        if process.is_alive():
            process.kill()
            await asyncio.to_thread(process.join, 3)


def _checkpoint_references(history: WorkflowHistory) -> list[PayloadReference] | None:
    """只读第一步完成事件的原始载荷封装，不通过 Codec 自动解包。"""
    scheduled = {
        event.event_id
        for event in history.events
        if event.event_type == EventType.EVENT_TYPE_ACTIVITY_TASK_SCHEDULED
        and event.activity_task_scheduled_event_attributes.activity_type.name == _PREPARE
    }
    completed = [
        event.activity_task_completed_event_attributes
        for event in history.events
        if event.event_type == EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED
        and event.activity_task_completed_event_attributes.scheduled_event_id in scheduled
    ]
    if len(scheduled) > 1 or len(completed) > 1:
        raise AssertionError("The same workflow must complete only one prepare activity")
    if not completed:
        return None
    return [
        PayloadReference.model_validate_json(payload.data)
        for payload in completed[0].result.payloads
        if payload.metadata.get("encoding") == ENCODING
    ]


async def wait_checkpoint(raw: Client, workflow_id: str) -> list[PayloadReference]:
    """明确等到数据库提交后的 Activity 输出也进入 Temporal 历史。"""
    handle = raw.get_workflow_handle(workflow_id)
    async with asyncio.timeout(40):
        while True:
            references = _checkpoint_references(
                await handle.fetch_history(rpc_timeout=_RPC_TIMEOUT)
            )
            if references is None:
                await asyncio.sleep(0.2)
                continue
            if len(references) != 1 or references[0].byte_size <= INLINE_LIMIT:
                raise AssertionError("The first step must have one external codec reference")
            return references


async def release(client: Client, workflow_id: str) -> None:
    await client.get_workflow_handle(workflow_id).signal(_RELEASE, rpc_timeout=_RPC_TIMEOUT)
