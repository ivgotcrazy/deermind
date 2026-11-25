"""稳定步骤结果；只在当前有效尝试及所有者业务事务内保存一次。

分层定位：foundation（公共运行底座 / 执行步骤）
对外契约：read/save 读取或保存稳定步骤结果，附输入哈希与所有者收据引用。
边界约束：读取旧候选仍检查当前资格；commit 只做本地业务提交，不调用模型；回滚整体回滚。
"""

import hashlib
import json
from collections.abc import Awaitable, Callable

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import Ref
from deermind.abstractions.executions import RunInput, StepResult
from deermind.foundation.system.executions import store
from deermind.foundation.system.executions.contracts import Registry
from deermind.foundation.system.executions.facts import record_change
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


def input_hash(value: object) -> str:
    """计算步骤输入的确定性哈希，用于复用候选时核对输入未被改写。"""
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


async def read(
    connection: AsyncConnection,
    registry: Registry,
    run: RunInput,
    *,
    name: str,
    occurrence: str,
    digest: str,
) -> StepResult | None:
    """读取旧候选也检查当前资格；失效尝试不能用读取绕开业务检查。"""
    await store.active(connection, registry, run, "step")
    row = (
        (
            await connection.execute(
                text(
                    "SELECT * FROM runtime.step_results WHERE execution_id=:id AND step_name=:name "
                    "AND occurrence_key=:occurrence"
                ),
                {"id": run.execution_id, "name": name, "occurrence": occurrence},
            )
        )
        .mappings()
        .one_or_none()
    )
    # 无该步骤历史结果，按未保存返回。
    if row is None:
        return None
    saved = StepResult.model_validate_json(json.dumps(dict(row), default=str))
    # 输入哈希与本次不符，说明候选被不同输入复用，判冲突。
    if saved.input_hash != digest:
        raise ValueError("Step input conflict")
    return saved


async def save(
    connection: AsyncConnection,
    registry: Registry,
    run: RunInput,
    *,
    name: str,
    occurrence: str,
    digest: str,
    commit: Callable[[AsyncConnection], Awaitable[tuple[Ref, Ref | None]]],
) -> StepResult:
    """commit只做本地业务提交，不调用模型；回滚时业务、Step和事实一起回滚。"""
    # 步骤名与发生位置标识均不能为空。
    if not name.strip() or not occurrence.strip():
        raise ValueError("Step name and occurrence are required")
    existing = await read(
        connection, registry, run, name=name, occurrence=occurrence, digest=digest
    )
    # 同步骤已有稳定结果：幂等读回，不重复提交业务。
    if existing is not None:
        return existing
    output, receipt = await commit(connection)
    now = await connection.scalar(text("SELECT clock_timestamp()"))
    saved = StepResult(
        execution_id=run.execution_id,
        step_name=name,
        occurrence_key=occurrence,
        input_hash=digest,
        output_ref=output,
        owner_receipt_ref=receipt,
        completed_by_attempt=run.attempt_id,
        created_at=now,
    )
    await connection.execute(
        text(
            "INSERT INTO runtime.step_results SELECT * FROM jsonb_populate_record("
            "NULL::runtime.step_results,CAST(:body AS jsonb))"
        ),
        {"body": saved.model_dump_json()},
    )
    execution = await store.load(connection, run.execution_id)
    granted = await store.authorization(connection, run.execution_id)
    await record_change(connection, execution, "progress_saved", granted.initiator_ref, step=saved)
    return saved
