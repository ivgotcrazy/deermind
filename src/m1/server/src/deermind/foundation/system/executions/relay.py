"""Worker 内派发与故障核对；远程查询在事务外，结束后由所有者共同收尾。

分层定位：foundation（公共运行底座 / 执行派发）
对外契约：dispatch_one 派发单条命令；reconcile 按服务端结束状态收尾；run_relay 启动派发与核对循环。
边界约束：失联或历史缺失留故障，不凭无响应判死；正常完成必须先保存正式结果，
Workflow 关闭不凭空生成结果。
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Dispatch, ExecutionNotFound, ExecutionTransport
from deermind.foundation.system.executions import commands, dispatch, store
from deermind.foundation.system.executions.contracts import Registry
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

LOGGER = logging.getLogger("runtime")


async def validate(engine: AsyncEngine, registry: Registry, command: Dispatch) -> bool:
    """核对固定登记和输入；返回启动是否仍有必要，不授予业务提交资格。"""
    async with engine.connect() as connection:
        saved = await store.load(connection, command.run.execution_id)
        current = await store.attempt(connection, command.run.attempt_id)
        entry = registry.resolve(saved)
        # 尝试归属、工作流、期限与固定工作的引用、登记类型/队列任一漂移，判派发不一致。
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
        # 仅当仍是当前有效尝试且工作处于可活动状态，本次派发才仍有必要。
        return saved.active_attempt_id == current.attempt_id and saved.state in {
            "ready",
            "running",
            "waiting",
        }


async def dispatch_one(
    engine: AsyncEngine, registry: Registry, transport: ExecutionTransport
) -> bool:
    """交接不等整项工作；停止资格已在PG落定，取消网络失败也不允许旧结果写入。"""
    lease = await dispatch.claim(engine, transport.limits)
    # 无可领取命令，本轮空闲返回。
    if lease is None:
        return False
    try:
        needed = await validate(engine, registry, lease.command)
        remaining = (lease.deadline - datetime.now(UTC)).total_seconds()
        run_id = None
        async with asyncio.timeout(min(transport.limits.request_seconds, max(0, remaining))):
            # 启动命令且仍需派发：交给执行传输拉起新运行。
            if lease.kind == "start" and needed:
                run_id = await transport.start(lease.command)
            # 信号命令且仍需派发：向已运行实例投递信号。
            elif lease.kind == "signal" and needed:
                await transport.signal(lease.command)
            # 取消命令：直接通知传输取消，不校验启动必要性。
            elif lease.kind == "cancel":
                try:
                    await transport.cancel(lease.command)
                except ExecutionNotFound:
                    # 未启动的取消不能当成已送达：等启动交接落定后再查。
                    async with engine.connect() as connection:
                        start_state = await connection.scalar(
                            text(
                                "SELECT state FROM runtime.handoffs WHERE kind='start' "
                                "AND logical_key=:key"
                            ),
                            {"key": str(lease.command.run.attempt_id)},
                        )
                    # 启动交接既未送达也未耗尽，取消结果不能视为确定，重新抛出留待重试。
                    if start_state not in {"delivered", "exhausted"}:
                        raise
        # 传输调用完成且未抛错，把交接标记成功并带回运行标识。
        await dispatch.finish(engine, lease, success=True, run_id=run_id)
    except Exception as error:
        # 派发未确认：交接记失败并保留原工作，不凭异常判定业务已死。
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
    engine: AsyncEngine,
    registry: Registry,
    transport: ExecutionTransport,
    after: UUID | None = None,
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
    # 逐条复查未结束工作；单条核对异常不影响同批其余条目。
    for row in rows:
        command = Dispatch.model_validate_json(json.dumps(row["payload"]))
        try:
            await validate(engine, registry, command)
            failure_code = None
            try:
                running = await transport.running(command)
            except ExecutionNotFound:
                # 已有真实运行记录却查不到，属传输侧异常，向上抛交由外层留故障。
                if row["temporal_run_id"] is not None:
                    raise
                # 无运行记录：交接已耗尽，或已过期限且启动未送达，判启动未找到。
                if row["dispatch_state"] == "exhausted" or (
                    command.run.deadline_at <= datetime.now(UTC)
                    and row["dispatch_state"] != "delivered"
                ):
                    failure_code = "START_NOT_FOUND"
            else:
                if not running:
                    # 正常业务完成必须先保存正式结果；仅Workflow关闭不能凭空生成结果。
                    failure_code = "WORKFLOW_CLOSED_WITHOUT_RESULT"
            # 已确定失败原因，在限定时限内落失败收尾。
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
            # 状态暂不可确认：保留原状态与业务，仅记错误日志，不重做业务。
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
    transport: ExecutionTransport,
    stopped: asyncio.Event,
) -> None:
    """同一Worker内的两个独立循环；退出保留所有持久安排。"""

    async def publish() -> None:
        """命令派发循环：每轮领取一条待派发命令交给执行传输。"""
        # 停止信号未置位前持续轮询，单轮异常不中断循环。
        while not stopped.is_set():
            try:
                await dispatch_one(engine, registry, transport)
            except Exception:
                LOGGER.exception(
                    "执行派发暂不可用", extra={"action": "execution_dispatch", "outcome": "failed"}
                )
            await asyncio.sleep(1)

    async def inspect() -> None:
        """执行状态核对循环：分批复查未结束工作的服务端状态并收尾。"""
        after = None
        # 按核对间隔分批推进；after 记录上批末条游标避免长任务占住范围。
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
        # 收到停止信号后取消两个循环并等待退出，持久化安排保留不动。
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
