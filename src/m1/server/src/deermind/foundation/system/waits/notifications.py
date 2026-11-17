"""订阅方保存唤醒安排；生产者无须知道有没有等待，以及谁在等。"""

from uuid import uuid4

from deermind.abstractions.delivery import Acceptance, EventNotice
from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Dispatch, Execution, RunInput
from deermind.abstractions.waits import Wait
from deermind.foundation.system.delivery.contracts import Subscription
from deermind.foundation.system.executions import store
from deermind.foundation.system.executions.contracts import Registry
from deermind.foundation.system.waits import facts
from deermind.foundation.system.waits.contracts import Policies
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def arrange(
    connection: AsyncConnection, entries: Registry, execution: Execution, wait: Wait, reason: str
) -> Ref:
    """同一等待、尝试、通知只登记一次；发给固定Workflow，不重新启动工作。"""
    if execution.active_attempt_id is None:
        raise ValueError("Wait has no execution attempt")
    current = await store.attempt(connection, execution.active_attempt_id)
    entry = entries.resolve(execution)
    command = Dispatch(
        wait_id=wait.wait_id,
        run=RunInput(
            execution_id=execution.execution_id,
            attempt_id=current.attempt_id,
            input_ref=execution.input_ref,
            implementation_ref=execution.implementation_ref,
            ai_config_ref=execution.ai_config_ref,
            deadline_at=current.deadline_at,
        ),
        workflow_id=current.workflow_id,
        workflow_type=entry.workflow_type,
        task_queue=entry.task_queue,
    )
    key = f"{wait.wait_id}:{current.attempt_id}:{reason}"
    source = Ref(owner="runtime", type="wait", id=str(wait.wait_id))
    await connection.execute(
        text(
            "INSERT INTO runtime.handoffs (handoff_id,kind,logical_key,source_ref,payload,state,"
            "next_attempt_at,created_at) VALUES (:id,'signal',:key,CAST(:source AS jsonb),"
            "CAST(:payload AS jsonb),'pending',clock_timestamp(),clock_timestamp()) "
            "ON CONFLICT (kind,logical_key) DO NOTHING"
        ),
        {
            "id": uuid4(),
            "key": key,
            "source": source.model_dump_json(),
            "payload": command.model_dump_json(),
        },
    )
    identity = await connection.scalar(
        text("SELECT handoff_id FROM runtime.handoffs WHERE kind='signal' AND logical_key=:key"),
        {"key": key},
    )
    return Ref(owner="runtime", type="handoff", id=str(identity))


def subscription(entries: Registry, policies: Policies) -> Subscription | None:
    """只订阅已接线业务声明的候选类型；没有业务登记时不造空订阅。"""
    if not policies.items:
        return None

    async def accept(connection: AsyncConnection, notice: EventNotice) -> Acceptance:
        # 接收器已核对正式事件；此处只查元数据，实际内容由业务probe授权读取。
        correlation = await connection.scalar(
            text("SELECT correlation_id FROM runtime.events WHERE event_id=:id"),
            {"id": notice.event_id},
        )
        identities = (
            await connection.scalars(
                text(
                    "SELECT w.wait_id FROM runtime.waits w JOIN runtime.executions e "
                    "ON e.execution_id=w.execution_id JOIN runtime.wait_handling h USING(wait_id) "
                    "WHERE w.resolution='pending' AND h.state='awaiting' "
                    "AND e.state IN ('ready','running','waiting') "
                    "AND w.condition->>'scope_id'=:scope AND w.condition->>'scope_kind'=:kind "
                    "AND (w.condition->'event_types') @> CAST(:types AS jsonb)"
                ),
                {
                    "scope": str(notice.scope_id),
                    "kind": notice.scope_kind,
                    "types": '["' + notice.event_type + '"]',
                },
            )
        ).all()
        refs: list[Ref] = []
        for identity in identities:
            wait = await facts.read_wait(connection, str(identity))
            execution = await store.load(connection, wait.execution_id)
            policies.resolve(wait, execution)
            values = {
                "event_id": str(notice.event_id),
                "producer": notice.producer,
                "correlation_id": str(correlation),
            }
            if all(values.get(k) == value for k, value in wait.condition.equals.items()):
                refs.append(
                    await arrange(connection, entries, execution, wait, str(notice.event_id))
                )
        return Acceptance(disposition="accepted" if refs else "ignored", arrangement_refs=refs)

    return Subscription(
        "runtime_waits",
        "1",
        frozenset(t for p in policies.items for t in p.event_types),
        frozenset(k for p in policies.items for k in p.scope_kinds),
        accept,
    )
