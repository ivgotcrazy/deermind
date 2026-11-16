"""等待只占Temporal历史；探测与接续在短Activity中运行，不占长连接。"""

import asyncio
import logging
from datetime import timedelta
from uuid import UUID

from deermind.foundation.system.executions import store
from deermind.foundation.system.executions.contracts import RunInput
from deermind.foundation.system.waits import facts, notifications
from deermind.foundation.system.waits.contracts import Handling, Wait, WaitCall
from deermind.foundation.system.waits.service import Waits
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

LOGGER = logging.getLogger("runtime")


class Activities:
    def __init__(self, engine: AsyncEngine, waits: Waits, *, timeout_seconds: int) -> None:
        self.engine, self.waits, self.timeout_seconds = engine, waits, timeout_seconds

    @activity.defn(name="runtime.wait_probe")
    async def probe(self, body: str) -> str:
        call = WaitCall.model_validate_json(body)
        try:
            async with asyncio.timeout(self.timeout_seconds), self.engine.begin() as connection:
                return (
                    await self.waits.probe(connection, call.run, call.wait_id)
                ).model_dump_json()
        except (ValueError, PermissionError) as error:
            raise ApplicationError(
                "Wait probe rejected", type=type(error).__name__, non_retryable=True
            ) from None

    @activity.defn(name="runtime.wait_handle")
    async def handle(self, body: str) -> str:
        call = WaitCall.model_validate_json(body)
        try:
            async with asyncio.timeout(self.timeout_seconds), self.engine.begin() as connection:
                return (
                    await self.waits.handle(connection, call.run, call.wait_id)
                ).model_dump_json()
        except (ValueError, PermissionError) as error:
            raise ApplicationError(
                "Wait handling rejected", type=type(error).__name__, non_retryable=True
            ) from None


class WaitSignals:
    """业务Workflow的signal函数转交receive；早到提示先保存，重复提示合并。"""

    def __init__(self) -> None:
        self.pending: set[str] = set()

    def receive(self, identity: str) -> None:
        self.pending.add(str(UUID(identity)))

    async def resume(
        self, call: WaitCall, *, activity_timeout: timedelta, retry_policy: RetryPolicy
    ) -> Handling:
        """先补查再挂起；Timer到期仍补查一次。Activity预算由所属工作给出。"""
        identity = str(call.wait_id)
        while True:
            self.pending.discard(identity)
            remaining = call.run.deadline_at - workflow.now()
            if remaining.total_seconds() <= 0:
                raise ApplicationError("Execution deadline expired", non_retryable=True)
            body = await workflow.execute_activity(
                "runtime.wait_probe",
                call.model_dump_json(),
                result_type=str,
                start_to_close_timeout=min(activity_timeout, remaining),
                schedule_to_close_timeout=remaining,
                retry_policy=retry_policy,
            )
            saved = Wait.model_validate_json(body)
            if saved.resolution != "pending":
                break
            remaining = saved.deadline_at - workflow.now()
            if remaining.total_seconds() > 0:
                try:
                    await workflow.wait_condition(
                        lambda: identity in self.pending, timeout=remaining
                    )
                except TimeoutError:
                    pass
        remaining = call.run.deadline_at - workflow.now()
        if remaining.total_seconds() <= 0:
            raise ApplicationError("No time left for continuation", non_retryable=True)
        body = await workflow.execute_activity(
            "runtime.wait_handle",
            call.model_dump_json(),
            result_type=str,
            start_to_close_timeout=min(activity_timeout, remaining),
            schedule_to_close_timeout=remaining,
            retry_policy=retry_policy,
        )
        result = Handling.model_validate_json(body)
        if result.state == "failed":
            raise ApplicationError("Wait continuation rejected", non_retryable=True)
        return result


async def reconcile(
    engine: AsyncEngine, waits: Waits, *, timeout_seconds: int, after: UUID | None = None
) -> UUID | None:
    """补查漏通知；每批100条，失败保留记录，不把读取失败当超时。"""
    async with engine.connect() as connection:
        identities = (
            await connection.scalars(
                text(
                    "SELECT w.wait_id FROM runtime.waits w "
                    "JOIN runtime.wait_handling h USING(wait_id) "
                    "JOIN runtime.executions e ON e.execution_id=w.execution_id "
                    "WHERE h.state IN ('awaiting','cancelled') "
                    "AND e.state IN ('ready','running','waiting') "
                    "AND (CAST(:after AS uuid) IS NULL OR w.wait_id>CAST(:after AS uuid)) "
                    "ORDER BY w.wait_id LIMIT 100"
                ),
                {"after": after},
            )
        ).all()
    for identity in identities:
        try:
            async with asyncio.timeout(timeout_seconds), engine.begin() as connection:
                saved = await facts.read_wait(connection, str(identity))
                execution = await store.load(connection, saved.execution_id)
                if execution.active_attempt_id is None:
                    continue
                current = await store.attempt(connection, execution.active_attempt_id)
                run = RunInput(
                    execution_id=execution.execution_id,
                    attempt_id=current.attempt_id,
                    input_ref=execution.input_ref,
                    implementation_ref=execution.implementation_ref,
                    ai_config_ref=execution.ai_config_ref,
                    deadline_at=current.deadline_at,
                )
                saved = await waits.probe(connection, run, identity)
                handling = await facts.read_handling(connection, saved)
                if saved.resolution != "pending" or handling.state == "cancelled":
                    await notifications.arrange(
                        connection, waits.entries, execution, saved, "reconcile:" + saved.resolution
                    )
        except Exception:
            LOGGER.exception(
                "等待补查失败，保留原等待",
                extra={
                    "action": "wait_reconcile",
                    "outcome": "failed",
                    "wait_id": str(identity),
                },
            )
    return identities[-1] if len(identities) == 100 else None


async def run_reconciler(
    engine: AsyncEngine,
    waits: Waits,
    stopped: asyncio.Event,
    *,
    interval: int,
    timeout_seconds: int,
) -> None:
    after = None
    while not stopped.is_set():
        try:
            after = await reconcile(engine, waits, timeout_seconds=timeout_seconds, after=after)
        except Exception:
            LOGGER.exception(
                "等待补查暂不可用",
                extra={
                    "action": "wait_reconcile",
                    "outcome": "failed",
                },
            )
        await asyncio.sleep(interval)
