"""工作与尝试的原子保存；远程执行、模型调用均不在此仓储内进行。"""

import json
from datetime import timedelta
from uuid import UUID, uuid4

from deermind.foundation.system.events.contracts import Ref
from deermind.foundation.system.executions.contracts import (
    Attempt,
    Authorization,
    Caller,
    Execution,
    Registry,
    RunInput,
    State,
)
from deermind.foundation.system.executions.facts import record_change
from deermind.foundation.system.waits.facts import cancel_execution
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def load(connection: AsyncConnection, execution_id: UUID, *, lock: bool = False) -> Execution:
    """内部读取；公开调用者须另验Caller，状态变更必须持工作行锁。"""
    query = "SELECT * FROM runtime.executions WHERE execution_id=:id"
    row = (
        (
            await connection.execute(
                text(query + (" FOR UPDATE" if lock else "")), {"id": execution_id}
            )
        )
        .mappings()
        .one()
    )
    return Execution.model_validate_json(json.dumps(dict(row), default=str))


async def attempt(connection: AsyncConnection, attempt_id: UUID) -> Attempt:
    row = (
        (
            await connection.execute(
                text("SELECT * FROM runtime.execution_attempts WHERE attempt_id=:id"),
                {"id": attempt_id},
            )
        )
        .mappings()
        .one()
    )
    return Attempt.model_validate_json(json.dumps(dict(row), default=str))


async def lock_owned(
    connection: AsyncConnection, registry: Registry, execution_id: UUID
) -> Execution:
    """不可变归属用于寻址；先业务锁、再执行锁，收尾不能反向获取业务锁。"""
    saved = await load(connection, execution_id)
    await registry.resolve(saved).lock(connection, saved.scope_kind, saved.scope_id)
    return await load(connection, execution_id, lock=True)


async def authorization(connection: AsyncConnection, execution_id: UUID) -> Authorization:
    row = (
        (
            await connection.execute(
                text("SELECT * FROM runtime.execution_authorizations WHERE execution_id=:id"),
                {"id": execution_id},
            )
        )
        .mappings()
        .one()
    )
    return Authorization.model_validate_json(json.dumps(dict(row), default=str))


async def check(
    connection: AsyncConnection,
    registry: Registry,
    execution: Execution,
    action: str,
) -> Authorization:
    """所存授权只是依据，所有者仍检查当前业务资格和资源。"""
    granted = await authorization(connection, execution.execution_id)
    if action not in granted.allowed_actions:
        raise PermissionError("Action was not granted to this work")
    await registry.resolve(execution).check(connection, execution, granted, action)
    return granted


async def arrange(
    connection: AsyncConnection,
    execution: Execution,
    current: Attempt,
    kind: str,
    registry: Registry,
    *,
    request_id: str | None = None,
) -> None:
    """命令内容随工作固定；取消仅针对指定尝试，不跨尝试寻址。"""
    entry = registry.resolve(execution)
    if kind == "cancel" and not request_id:
        raise ValueError("Cancellation must identify its request")
    body = RunInput(
        execution_id=execution.execution_id,
        attempt_id=current.attempt_id,
        input_ref=execution.input_ref,
        implementation_ref=execution.implementation_ref,
        ai_config_ref=execution.ai_config_ref,
        deadline_at=current.deadline_at,
    )
    payload = {
        "run": body.model_dump(mode="json"),
        "workflow_id": current.workflow_id,
        "workflow_type": entry.workflow_type,
        "task_queue": entry.task_queue,
    }
    await connection.execute(
        text(
            "INSERT INTO runtime.handoffs (handoff_id,kind,logical_key,source_ref,payload,state,"
            "next_attempt_at,created_at) VALUES (:id,:kind,:key,CAST(:source AS jsonb),"
            "CAST(:payload AS jsonb),'pending',clock_timestamp(),clock_timestamp()) "
            "ON CONFLICT (kind,logical_key) DO NOTHING"
        ),
        {
            "id": uuid4(),
            "kind": kind,
            "key": f"{request_id}:{current.attempt_id}"
            if kind == "cancel"
            else str(current.attempt_id),
            "source": Ref(
                owner="runtime", type="execution", id=str(execution.execution_id)
            ).model_dump_json(),
            "payload": json.dumps(payload),
        },
    )


async def new_attempt(
    connection: AsyncConnection,
    execution: Execution,
    seconds: int,
    retry_request_id: str | None = None,
) -> Attempt:
    """在原工作锁内追加；期限从受理算起，派发及排队消耗同一份时间。"""
    if type(seconds) is not int or seconds <= 0:
        raise ValueError("A finite positive execution budget is required")
    identity = uuid4()
    number = await connection.scalar(
        text(
            "SELECT COALESCE(max(attempt_no),0)+1 FROM runtime.execution_attempts "
            "WHERE execution_id=:id"
        ),
        {"id": execution.execution_id},
    )
    await connection.execute(
        text(
            "INSERT INTO runtime.execution_attempts "
            "(attempt_id,execution_id,attempt_no,retry_request_id,previous_attempt_id,workflow_id,"
            "accepted_at,deadline_at,state) VALUES "
            "(:id,:execution,:number,:request,:previous,:workflow,"
            "clock_timestamp(),clock_timestamp()+:budget,'ready')"
        ),
        {
            "id": identity,
            "execution": execution.execution_id,
            "number": number,
            "request": retry_request_id,
            "previous": execution.active_attempt_id,
            "workflow": f"dm/{execution.execution_id}/{identity}",
            "budget": timedelta(seconds=seconds),
        },
    )
    await connection.execute(
        text(
            "UPDATE runtime.executions SET active_attempt_id=:attempt,state='ready',"
            "failure_ref=NULL,updated_at=clock_timestamp() WHERE execution_id=:id"
        ),
        {"attempt": identity, "id": execution.execution_id},
    )
    # 结果身份不变，恢复只追加本次生产尝试；已有成功结果不重复生产。
    await connection.execute(
        text(
            "INSERT INTO runtime.result_attempts "
            "(scope_id,trigger_event_id,producer,result_kind,attempt_id,outcome,created_at) "
            "SELECT r.scope_id,r.trigger_event_id,r.producer,r.result_kind,:attempt,'pending',"
            "clock_timestamp() FROM runtime.expected_results r WHERE r.execution_id=:id "
            "AND NOT EXISTS (SELECT 1 FROM runtime.published_results p WHERE "
            "(p.scope_id,p.trigger_event_id,p.producer,p.result_kind)="
            "(r.scope_id,r.trigger_event_id,r.producer,r.result_kind))"
        ),
        {"attempt": identity, "id": execution.execution_id},
    )
    return await attempt(connection, identity)


async def accept(
    connection: AsyncConnection,
    registry: Registry,
    caller: Caller,
    *,
    entry_name: str,
    scope_kind: str,
    scope_id: UUID,
    acceptance_key: str,
    input_ref: Ref,
    seconds: int,
    basis_refs: list[Ref],
    ai_config_ref: UUID | None = None,
    commit_id: UUID | None = None,
) -> Execution:
    """同键返回原工作，异输入拒绝；调用方负责和业务收据共同提交或回滚。"""
    if not connection.in_transaction() or not acceptance_key.strip():
        raise ValueError("An active transaction and acceptance key are required")
    entry = registry.entries[entry_name]
    if (entry.kind == "ai_operation") != (ai_config_ref is not None):
        raise ValueError("AI configuration must match the registered work kind")
    await entry.lock(connection, scope_kind, scope_id)
    # 同一受理键只有一个创建者，首次尚无工作行时也能串行。
    key = json.dumps([entry.owner, entry_name, str(scope_id), acceptance_key])
    await connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": "execution:" + key}
    )
    existing = await connection.scalar(
        text(
            "SELECT execution_id FROM runtime.executions WHERE owner=:owner AND entry_ref=:entry "
            "AND scope_id=:scope AND acceptance_key=:key"
        ),
        {"owner": entry.owner, "entry": entry_name, "scope": scope_id, "key": acceptance_key},
    )
    if existing is not None:
        saved = await load(connection, existing, lock=True)
        caller.require(saved, "accept")
        if saved.scope_kind != scope_kind or saved.input_ref != input_ref:
            raise ValueError("Execution identity conflict")
        await check(connection, registry, saved, "read")
        return saved

    # AI配置表以execution_id为主键；受理方预分配此身份并在同一事务固定配置。
    identity = ai_config_ref if ai_config_ref is not None else uuid4()
    now = await connection.scalar(text("SELECT clock_timestamp()"))
    saved = Execution(
        execution_id=identity,
        kind=entry.kind,
        owner=entry.owner,
        entry_ref=entry_name,
        scope_kind=scope_kind,
        implementation_ref=entry.implementation_ref,
        ai_config_ref=ai_config_ref,
        scope_id=scope_id,
        acceptance_key=acceptance_key,
        input_ref=input_ref,
        active_attempt_id=None,
        state="ready",
        result_ref=None,
        failure_ref=None,
        created_at=now,
        updated_at=now,
    )
    caller.require(saved, "accept")
    granted = Authorization(
        execution_id=identity,
        initiator_ref=caller.actor,
        owner=entry.owner,
        entry=entry_name,
        resource_scope={"kind": scope_kind, "id": str(scope_id)},
        allowed_actions=["read", "start", "step", "finish", "retry", "cancel"],
        basis_refs=basis_refs,
        created_at=now,
    )
    await entry.check(connection, saved, granted, "accept")
    await connection.execute(
        text(
            "INSERT INTO runtime.executions SELECT * FROM jsonb_populate_record("
            "NULL::runtime.executions,CAST(:body AS jsonb))"
        ),
        {"body": saved.model_dump_json()},
    )
    await connection.execute(
        text(
            "INSERT INTO runtime.execution_authorizations SELECT * FROM jsonb_populate_record("
            "NULL::runtime.execution_authorizations,CAST(:body AS jsonb))"
        ),
        {"body": granted.model_dump_json()},
    )
    current = await new_attempt(connection, saved, seconds)
    saved = await load(connection, identity)
    await arrange(connection, saved, current, "start", registry)
    await record_change(
        connection, saved, "accepted", caller.actor, attempt=current, commit_id=commit_id
    )
    return saved


async def active(
    connection: AsyncConnection,
    registry: Registry,
    run: RunInput,
    action: str,
) -> Execution:
    """先锁工作再检查身份和期限；旧尝试的任何业务提交都必须经过这里。"""
    saved = await lock_owned(connection, registry, run.execution_id)
    current = await attempt(connection, run.attempt_id)
    if (
        saved.active_attempt_id != run.attempt_id
        or saved.state not in {"ready", "running", "waiting"}
        or saved.input_ref != run.input_ref
        or saved.implementation_ref != run.implementation_ref
        or saved.ai_config_ref != run.ai_config_ref
        or current.deadline_at != run.deadline_at
        or current.deadline_at <= await connection.scalar(text("SELECT clock_timestamp()"))
    ):
        raise ValueError("Execution attempt is stale, stopped, or expired")
    await check(connection, registry, saved, action)
    return saved


async def close(
    connection: AsyncConnection,
    registry: Registry,
    execution: Execution,
    state: State,
    actor: Ref,
    *,
    result_ref: Ref | None = None,
    failure_ref: Ref | None = None,
    request_id: str | None = None,
) -> Execution:
    """持工作锁时调用；业务收尾失败则整次回滚，不能只保存公共完成状态。"""
    if state not in {"completed", "failed", "cancelled"}:
        raise ValueError("A terminal state is required")
    if state == "cancelled":
        await cancel_execution(connection, execution.execution_id, actor)
    await registry.resolve(execution).finalize(
        connection, execution, state, result_ref or failure_ref
    )
    if state == "completed" and await connection.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM runtime.result_attempts "
            "WHERE attempt_id=:id AND outcome='pending')"
        ),
        {"id": execution.active_attempt_id},
    ):
        raise ValueError("Expected results must be published before completion")
    await connection.execute(
        text(
            "UPDATE runtime.result_attempts SET outcome=:state,failure_ref=CAST(:failure AS jsonb),"
            "finished_at=clock_timestamp() WHERE attempt_id=:id AND outcome='pending'"
        ),
        {
            "state": state,
            "id": execution.active_attempt_id,
            "failure": failure_ref.model_dump_json() if failure_ref else None,
        },
    )
    await connection.execute(
        text(
            "UPDATE runtime.executions SET state=:state,result_ref=CAST(:result AS jsonb),"
            "failure_ref=CAST(:failure AS jsonb),updated_at=clock_timestamp() "
            "WHERE execution_id=:id"
        ),
        {
            "id": execution.execution_id,
            "state": state,
            "result": result_ref.model_dump_json() if result_ref else None,
            "failure": failure_ref.model_dump_json() if failure_ref else None,
        },
    )
    await connection.execute(
        text(
            "UPDATE runtime.execution_attempts SET state=:state,"
            "failure_ref=CAST(:failure AS jsonb),"
            "finished_at=clock_timestamp() WHERE attempt_id=:id"
        ),
        {
            "id": execution.active_attempt_id,
            "state": state,
            "failure": failure_ref.model_dump_json() if failure_ref else None,
        },
    )
    saved = await load(connection, execution.execution_id)
    assert saved.active_attempt_id is not None
    current = await attempt(connection, saved.active_attempt_id)
    outcome = "completed" if state == "completed" else "failed" if state == "failed" else "stopped"
    await record_change(connection, saved, outcome, actor, attempt=current, request_id=request_id)
    return saved
