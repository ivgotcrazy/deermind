"""等待控制留痕；不参与业务投影重建，也不重新投递成教学动作。

分层定位：foundation（公共运行底座 / 等待留痕）
对外契约：WaitChanged 事件记录等待与接续状态；record/read_wait/read_handling 承接留痕与读取。
边界约束：只维护 runtime 等待控制记录，不参与投影重建，也不把等待事件重投为业务动作。
"""

import json
from typing import Literal
from uuid import UUID, uuid4

from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactRecord,
    InlineContent,
    ProducerAccess,
    Ref,
)
from deermind.abstractions.waits import Handling, Wait
from deermind.foundation.system.events.store import EventStore
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# 等待状态结果取值。
Outcome = Literal["registered", "matched", "timed_out", "cancelled", "handled"]


class WaitChanged(EventPayload):
    """等待状态变更事件正文：主体、结果与原因码。"""

    subject_ref: Ref
    outcome: Outcome
    reason_code: str | None


def validate(draft: EventDraft, payload: EventPayload) -> None:
    """校验等待事件的主体、记录基数与等待/接续身份一致。"""
    # 正文类型与归属主体必须与事件所有者一致。
    if not isinstance(payload, WaitChanged) or payload.subject_ref != draft.owner_ref:
        raise ValueError("Invalid wait event")
    # 按表名拆出等待记录与接续记录。
    waits = [r for r in payload.records if r.record_type == "runtime.waits"]
    handlers = [r for r in payload.records if r.record_type == "runtime.wait_handling"]
    # 恰好一条等待记录，接续记录至多一条，且不能夹带其他表记录。
    if len(waits) != 1 or len(handlers) > 1 or len(payload.records) != 1 + len(handlers):
        raise ValueError("Invalid wait record cardinality")
    if not isinstance(waits[0].content, InlineContent):
        raise ValueError("Decoded wait fact required")
    wait = Wait.model_validate_json(json.dumps(waits[0].content.value))
    # 等待必须属于本范围，且事件主体与等待编号一致。
    if wait.execution_id != draft.scope_id or draft.owner_ref != Ref(
        owner="runtime", type="wait", id=str(wait.wait_id)
    ):
        raise ValueError("Wait fact belongs to another work")
    # 逐条接续记录核对其归属等待与接续动作。
    for record in handlers:
        if not isinstance(record.content, InlineContent):
            raise ValueError("Decoded handling fact required")
        handling = Handling.model_validate_json(json.dumps(record.content.value))
        # 接续须挂在同一等待上，且恢复动作与等待登记的一致。
        if handling.wait_id != wait.wait_id or handling.resume_action_id != wait.resume_action_id:
            raise ValueError("Handling identity mismatch")


# WaitStateChanged 事件的类型、版本、生产者、范围与记录 Schema 登记。
REGISTRATION = EventRegistration(
    "WaitStateChanged",
    1,
    "runtime",
    "execution",
    WaitChanged,
    validate,
    {("runtime.waits", 1): Wait, ("runtime.wait_handling", 1): Handling},
)


async def record(
    connection: AsyncConnection, wait: Wait, handling: Handling, outcome: Outcome, actor: Ref
) -> None:
    """调用方持Wait锁；记录、决定及业务接续共同提交。"""
    owner = Ref(owner="runtime", type="wait", id=str(wait.wait_id))
    payload = WaitChanged(
        subject_ref=owner,
        outcome=outcome,
        # 接续失败才带原因码，其余结果不留原因。
        reason_code="HANDLING_FAILED" if handling.state == "failed" else None,
        records=[
            FactRecord(
                record_id=name,
                record_type="runtime." + name,
                schema_version=1,
                content=InlineContent(storage="inline", value=model.model_dump(mode="json")),
            )
            for name, model in (("waits", wait), ("wait_handling", handling))
        ],
    )
    scope = ("execution", wait.execution_id)
    sequence = await connection.scalar(
        text(
            "SELECT last_seq FROM runtime.scope_event_heads "
            "WHERE scope_kind='execution' AND scope_id=:id"
        ),
        {"id": wait.execution_id},
    )
    await EventStore([REGISTRATION]).append(
        connection,
        ProducerAccess("runtime", actor, frozenset({scope})),
        [
            EventDraft(
                uuid4(),
                "WaitStateChanged",
                1,
                *scope,
                owner,
                payload.model_dump(mode="json"),
                str(wait.resume_action_id),
                source_execution_ref=wait.execution_id,
            )
        ],
        commit_id=uuid4(),
        correlation_id=wait.execution_id,
        expected_seq={scope: sequence or 0},
    )


async def read_wait(connection: AsyncConnection, identity: str, *, lock: bool = False) -> Wait:
    """按等待编号读取等待记录；lock 为真时取行锁。"""
    row = (
        (
            await connection.execute(
                text(
                    "SELECT * FROM runtime.waits WHERE wait_id=:id"
                    # 持锁读取加 FOR UPDATE，供同事务内串行修改等待记录。
                    + (" FOR UPDATE" if lock else "")
                ),
                {"id": identity},
            )
        )
        .mappings()
        .one()
    )
    return Wait.model_validate_json(json.dumps(dict(row), default=str))


async def read_handling(connection: AsyncConnection, wait: Wait) -> Handling:
    """按等待编号读取其接续记录。"""
    row = (
        (
            await connection.execute(
                text("SELECT * FROM runtime.wait_handling WHERE wait_id=:id"), {"id": wait.wait_id}
            )
        )
        .mappings()
        .one()
    )
    return Handling.model_validate_json(json.dumps(dict(row), default=str))


async def cancel_execution(connection: AsyncConnection, execution_id: UUID, actor: Ref) -> None:
    """调用者已持执行锁；整项停止只取消尚未提交的接续，保留原已落定决定。"""
    identities = (
        await connection.scalars(
            text(
                "SELECT w.wait_id FROM runtime.waits w JOIN runtime.wait_handling h USING(wait_id) "
                "WHERE w.execution_id=:id AND h.state IN ('awaiting','failed') "
                "ORDER BY w.wait_id FOR UPDATE OF w"
            ),
            {"id": execution_id},
        )
    ).all()
    # 逐条取消尚未提交的接续；已落定的决定保留不动。
    for identity in identities:
        await connection.execute(
            text(
                "UPDATE runtime.waits SET resolution='cancelled',resolved_at=clock_timestamp() "
                "WHERE wait_id=:id AND resolution='pending'"
            ),
            {"id": identity},
        )
        await connection.execute(
            text(
                "UPDATE runtime.wait_handling SET state='cancelled',failure_ref=NULL,"
                "updated_at=clock_timestamp() WHERE wait_id=:id"
            ),
            {"id": identity},
        )
        saved = await read_wait(connection, str(identity))
        await record(connection, saved, await read_handling(connection, saved), "cancelled", actor)
