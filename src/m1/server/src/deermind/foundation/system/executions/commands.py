"""停止与获准恢复；始终保留原工作、授权、输入、配置和已完成步骤。"""

from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Execution, RunInput
from deermind.foundation.system.executions import store
from deermind.foundation.system.executions.contracts import Caller, Registry
from deermind.foundation.system.executions.facts import record_change
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def read(
    connection: AsyncConnection,
    registry: Registry,
    caller: Caller,
    execution_id: UUID,
) -> Execution:
    saved = await store.load(connection, execution_id)
    caller.require(saved, "read")
    await store.check(connection, registry, saved, "read")
    return saved


async def start(
    connection: AsyncConnection,
    registry: Registry,
    run: RunInput,
) -> Execution:
    """重复开始不另记事实；当前尝试必须仍有效。"""
    saved = await store.active(connection, registry, run, "start")
    if saved.state == "running":
        return saved
    await connection.execute(
        text(
            "UPDATE runtime.executions SET state='running',updated_at=clock_timestamp() "
            "WHERE execution_id=:id"
        ),
        {"id": saved.execution_id},
    )
    await connection.execute(
        text("UPDATE runtime.execution_attempts SET state='running' WHERE attempt_id=:id"),
        {"id": run.attempt_id},
    )
    saved = await store.load(connection, saved.execution_id)
    granted = await store.authorization(connection, saved.execution_id)
    await record_change(
        connection,
        saved,
        "started",
        granted.initiator_ref,
        attempt=await store.attempt(connection, run.attempt_id),
    )
    return saved


async def complete(
    connection: AsyncConnection,
    registry: Registry,
    run: RunInput,
    result: Ref,
) -> Execution:
    """结果已提交而Activity回应丢失时，返回原结果而不重复业务收尾。"""
    saved = await store.lock_owned(connection, registry, run.execution_id)
    if saved.state == "completed" and saved.active_attempt_id == run.attempt_id:
        if saved.result_ref != result:
            raise ValueError("Completed result conflict")
        return saved
    saved = await store.active(connection, registry, run, "finish")
    granted = await store.authorization(connection, saved.execution_id)
    return await store.close(
        connection, registry, saved, "completed", granted.initiator_ref, result_ref=result
    )


async def fail(
    connection: AsyncConnection,
    registry: Registry,
    run: RunInput,
    failure: Ref,
) -> Execution:
    """执行结束或已确认耗尽后的收尾；允许过期，但不覆盖新尝试或停止。"""
    saved = await store.lock_owned(connection, registry, run.execution_id)
    if saved.active_attempt_id != run.attempt_id or saved.state in {
        "completed",
        "failed",
        "cancelled",
    }:
        return saved
    registry.resolve(saved)
    granted = await store.authorization(connection, saved.execution_id)
    return await store.close(
        connection, registry, saved, "failed", granted.initiator_ref, failure_ref=failure
    )


async def cancel(
    connection: AsyncConnection,
    registry: Registry,
    caller: Caller,
    execution_id: UUID,
    *,
    request_id: str,
) -> Execution:
    """先废止提交资格并由所有者收尾，再登记指定尝试的取消命令。"""
    if not request_id.strip():
        raise ValueError("A cancellation request ID is required")
    saved = await store.lock_owned(connection, registry, execution_id)
    caller.require(saved, "cancel")
    await store.check(connection, registry, saved, "cancel")
    if saved.state in {"completed", "failed", "cancelled"}:
        return saved
    saved = await store.close(
        connection, registry, saved, "cancelled", caller.actor, request_id=request_id
    )
    assert saved.active_attempt_id is not None
    current = await store.attempt(connection, saved.active_attempt_id)
    await store.arrange(connection, saved, current, "cancel", registry, request_id=request_id)
    return saved


async def retry(
    connection: AsyncConnection,
    registry: Registry,
    caller: Caller,
    execution_id: UUID,
    *,
    request_id: str,
    seconds: int,
) -> Execution:
    """同恢复键不续期；仅failed可恢复，额度由所有者按原execution检查。"""
    if not request_id.strip():
        raise ValueError("A recovery request ID is required")
    saved = await store.lock_owned(connection, registry, execution_id)
    caller.require(saved, "retry")
    previous = await connection.scalar(
        text(
            "SELECT attempt_id FROM runtime.execution_attempts WHERE execution_id=:id "
            "AND retry_request_id=:request"
        ),
        {"id": execution_id, "request": request_id},
    )
    if previous is not None:
        await store.check(connection, registry, saved, "read")
        return saved
    if saved.state != "failed":
        raise ValueError("Only failed work can be recovered")
    await store.check(connection, registry, saved, "retry")
    current = await store.new_attempt(connection, saved, seconds, request_id)
    saved = await store.load(connection, execution_id)
    await store.arrange(connection, saved, current, "start", registry)
    await record_change(connection, saved, "recovery_accepted", caller.actor, attempt=current)
    return saved
