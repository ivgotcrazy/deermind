"""稳定步骤结果；只在当前有效尝试及所有者业务事务内保存一次。"""

import hashlib
import json
from collections.abc import Awaitable, Callable

from deermind.foundation.system.events.contracts import Ref
from deermind.foundation.system.events.store import canonical_json
from deermind.foundation.system.executions import store
from deermind.foundation.system.executions.contracts import Registry, RunInput, StepResult
from deermind.foundation.system.executions.facts import record_change
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


def input_hash(value: object) -> str:
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
    if row is None:
        return None
    saved = StepResult.model_validate_json(json.dumps(dict(row), default=str))
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
    if not name.strip() or not occurrence.strip():
        raise ValueError("Step name and occurrence are required")
    existing = await read(
        connection, registry, run, name=name, occurrence=occurrence, digest=digest
    )
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
