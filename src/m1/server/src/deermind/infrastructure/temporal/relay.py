"""Worker内派发与故障核对；远程查询在事务外，结束后由所有者共同收尾。"""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from deermind.foundation.system.events.contracts import Ref
from deermind.foundation.system.executions import commands, dispatch, store
from deermind.foundation.system.executions.contracts import Dispatch, Registry
from deermind.infrastructure.temporal.executions import Transport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio.client import WorkflowExecutionStatus
from temporalio.service import RPCError, RPCStatusCode

LOGGER = logging.getLogger("runtime")


async def validate(engine: AsyncEngine, registry: Registry, command: Dispatch) -> bool:
    """核对固定登记和输入；返回启动是否仍有必要，不授予业务提交资格。"""
    async with engine.connect() as connection:
        saved = await store.load(connection, command.run.execution_id)
        current = await store.attempt(connection, command.run.attempt_id)
        entry = registry.resolve(saved)
        if (
            current.execution_id != saved.execution_id
            or current.workflow_id != command.workflow_id
            or current.deadline_at != command.run.deadline_at
            or command.run.input_ref != saved.input_ref
            or command.run.ai_config_ref != saved.ai_config_ref
            or command.run.implementation_ref != saved.implementation_ref
            or entry.workflow_type != command.workflow_type
            or entry.task_queue != command.task_queue
        ):
            raise ValueError("Saved dispatch differs from the registered execution")
        return saved.active_attempt_id == current.attempt_id and saved.state in {
            "ready",
            "running",
            "waiting",
        }


async def dispatch_one(engine: AsyncEngine, registry: Registry, transport: Transport) -> bool:
    """交接不等整项工作；停止资格已在PG落定，取消网络失败也不允许旧结果写入。"""
    lease = await dispatch.claim(engine, transport.limits)
    if lease is None:
        return False
    try:
        needed = await validate(engine, registry, lease.command)
        remaining = (lease.deadline - datetime.now(UTC)).total_seconds()
        run_id = None
        async with asyncio.timeout(min(transport.limits.request_seconds, max(0, remaining))):
            if lease.kind == "start" and needed:
                run_id = await transport.start(lease.command)
            elif lease.kind == "cancel":
                try:
                    await transport.cancel(lease.command)
                except RPCError as error:
                    if error.status != RPCStatusCode.NOT_FOUND:
                        raise
                    # 未启动的取消不能当成已送达：等启动交接落定后再查。
                    async with engine.connect() as connection:
                        start_state = await connection.scalar(
                            text(
                                "SELECT state FROM runtime.handoffs WHERE kind='start' "
                                "AND logical_key=:key"
                            ),
                            {"key": str(lease.command.run.attempt_id)},
                        )
                    if start_state not in {"delivered", "exhausted"}:
                        raise
        await dispatch.finish(engine, lease, success=True, run_id=run_id)
    except Exception as error:
        await dispatch.finish(engine, lease, success=False, error_code=type(error).__name__)
        LOGGER.warning(
            "执行命令尚未确认，原工作和交接记录保留",
            extra={
                "action": "execution_dispatch",
                "outcome": "pending",
                "execution_id": str(lease.command.run.execution_id),
                "handoff_id": str(lease.handoff_id),
                "error_code": type(error).__name__,
            },
        )
    return True


async def reconcile(
    engine: AsyncEngine, registry: Registry, transport: Transport, after: UUID | None = None
) -> UUID | None:
    """只按服务端结束状态收尾；失联或历史缺失留故障，不凭无响应判死。"""
    async with engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        "SELECT e.execution_id,h.payload,h.state AS dispatch_state,"
                        "a.temporal_run_id "
                        "FROM runtime.executions e JOIN runtime.execution_attempts a "
                        "ON a.attempt_id=e.active_attempt_id JOIN runtime.handoffs h "
                        "ON h.kind='start' AND h.logical_key=CAST(a.attempt_id AS text) "
                        "WHERE e.state IN ('ready','running','waiting') "
                        "AND (CAST(:after AS uuid) IS NULL OR e.execution_id>CAST(:after AS uuid)) "
                        "ORDER BY e.execution_id LIMIT 100"
                    ),
                    {"after": after},
                )
            )
            .mappings()
            .all()
        )
    for row in rows:
        command = Dispatch.model_validate_json(json.dumps(row["payload"]))
        try:
            await validate(engine, registry, command)
            failure_code = None
            try:
                description = await transport.client.get_workflow_handle(
                    command.workflow_id
                ).describe(rpc_timeout=timedelta(seconds=transport.limits.request_seconds))
            except RPCError as error:
                if error.status != RPCStatusCode.NOT_FOUND or row["temporal_run_id"] is not None:
                    raise
                if row["dispatch_state"] == "exhausted" or (
                    command.run.deadline_at <= datetime.now(UTC)
                    and row["dispatch_state"] != "delivered"
                ):
                    failure_code = "START_NOT_FOUND"
            else:
                if (
                    await description.memo_value("deermind_input", type_hint=str)
                    != command.run.model_dump_json()
                ):
                    raise ValueError("Workflow input differs from the saved work")
                if description.status != WorkflowExecutionStatus.RUNNING:
                    # 正常业务完成必须先保存正式结果；仅Workflow关闭不能凭空生成结果。
                    failure_code = "WORKFLOW_CLOSED_WITHOUT_RESULT"
            if failure_code:
                async with (
                    asyncio.timeout(transport.limits.finalize_seconds),
                    engine.begin() as connection,
                ):
                    await commands.fail(
                        connection,
                        registry,
                        command.run,
                        Ref(
                            owner="runtime",
                            type="execution_failure",
                            id=str(command.run.attempt_id),
                            path=failure_code,
                        ),
                    )
        except Exception as error:
            LOGGER.error(
                "执行结束状态待核对，保留原状态，不重做业务",
                extra={
                    "action": "execution_reconcile",
                    "outcome": "failed",
                    "execution_id": str(command.run.execution_id),
                    "error_code": type(error).__name__,
                },
            )
    # 按批轮巡，避免前100个长任务一直占住核对范围；重启从头核对也安全。
    return rows[-1]["execution_id"] if len(rows) == 100 else None


async def run_relay(
    engine: AsyncEngine,
    registry: Registry,
    transport: Transport,
    stopped: asyncio.Event,
) -> None:
    """同一Worker内的两个独立循环；退出保留所有持久安排。"""

    async def publish() -> None:
        while not stopped.is_set():
            try:
                await dispatch_one(engine, registry, transport)
            except Exception:
                LOGGER.exception(
                    "执行派发暂不可用", extra={"action": "execution_dispatch", "outcome": "failed"}
                )
            await asyncio.sleep(1)

    async def inspect() -> None:
        after = None
        while not stopped.is_set():
            try:
                after = await reconcile(engine, registry, transport, after)
            except Exception:
                LOGGER.exception(
                    "执行核对暂不可用", extra={"action": "execution_reconcile", "outcome": "failed"}
                )
            await asyncio.sleep(transport.limits.reconcile_seconds)

    tasks = [asyncio.create_task(publish()), asyncio.create_task(inspect())]
    try:
        await stopped.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
