"""发布安排、短租约和重试预算；远程发布始终在事务外执行。

分层定位：foundation（公共运行底座 / 事件交接）
对外契约：Outbox.arrange 生成交接安排；claim 领取租约；finish 落定结果；mark_failure 登记故障。
边界约束：租约过期可接手；重试次数与总时长预算不因进程重启清零；晚到确认不能覆盖后来持有者。
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from deermind.abstractions.delivery import EventNotice, Handoff
from deermind.abstractions.events import Ref, StoredEvent
from deermind.foundation.system.delivery.contracts import SubscriptionRegistry
from deermind.foundation.system.delivery.facts import record_change
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


@dataclass(frozen=True)
class Lease:
    """一次已领取的租约：交接记录、尝试号、持有者与截止时间。"""

    handoff: Handoff
    attempt_no: int
    owner: str
    deadline: datetime


async def delivery_state(connection: AsyncConnection, event_id: UUID) -> str | None:
    """按 delivery_id 取最新发布交接状态。"""
    return await connection.scalar(
        text(
            "SELECT state FROM runtime.handoffs WHERE kind='publish' AND delivery_id=:event "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"event": event_id},
    )


class Outbox:
    """固定应接收方后再交接；无订阅的审计事实仅保存在数据库。"""

    def __init__(self, registry: SubscriptionRegistry) -> None:
        self.registry = registry

    async def arrange(self, connection: AsyncConnection, event: StoredEvent) -> None:
        """按订阅快照固定应接收方并生成待发布交接；无订阅则不留交接安排。"""
        subscribers = self.registry.matching(event.draft.event_type, event.draft.scope_kind)
        # 无在册订阅者：审计事实只留在数据库，不生成待发布交接。
        if not subscribers:
            return
        identity = uuid4()
        notice = EventNotice(
            handoff_id=identity,
            delivery_id=event.draft.event_id,
            event_id=event.draft.event_id,
            event_type=event.draft.event_type,
            schema_version=event.draft.schema_version,
            producer=await connection.scalar(
                text("SELECT producer FROM runtime.events WHERE event_id=:id"),
                {"id": event.draft.event_id},
            ),
            scope_kind=event.draft.scope_kind,
            scope_id=event.draft.scope_id,
        )
        await connection.execute(
            text(
                "INSERT INTO runtime.handoffs "
                "(handoff_id,kind,logical_key,source_ref,payload,state,next_attempt_at,"
                "subscription_snapshot,delivery_id,created_at) VALUES "
                "(:id,'publish',:key,CAST(:source AS jsonb),CAST(:payload AS jsonb),'pending',"
                "clock_timestamp(),CAST(:subscribers AS jsonb),:delivery,clock_timestamp())"
            ),
            {
                "id": identity,
                "key": f"{event.draft.event_id}:initial",
                "source": Ref(
                    owner="runtime", type="event", id=str(event.draft.event_id)
                ).model_dump_json(),
                "payload": notice.model_dump_json(),
                "delivery": notice.delivery_id,
                "subscribers": json.dumps(
                    {item.subscriber_id: item.revision for item in subscribers}
                ),
            },
        )
        await record_change(connection, identity, "arranged", commit_id=event.commit_id)


async def claim(engine: AsyncEngine, owner: str) -> Lease | None:
    """租约过期可接手；从第一次尝试起计总预算，不因进程重启清零。"""
    async with engine.begin() as connection:
        # 可领取：待发布已到重试点，或在租约已过期被其他进程接手；SKIP LOCKED 避免互相等待。
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT * FROM runtime.handoffs WHERE kind='publish' AND "
                        "((state='pending' AND next_attempt_at<=clock_timestamp()) OR "
                        "(state='leased' AND lease_until<=clock_timestamp())) "
                        "ORDER BY next_attempt_at,handoff_id FOR UPDATE SKIP LOCKED LIMIT 1"
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        # 没有可领取的交接，本轮空转。
        if row is None:
            return None
        handoff = Handoff.model_validate_json(json.dumps(dict(row), default=str))
        # 累计尝试次数与首次开始时间，用于次数与总时长双重重试预算判定。
        attempts = (
            await connection.execute(
                text(
                    "SELECT count(*),min(started_at) FROM runtime.handoff_attempts WHERE "
                    "handoff_id=:id"
                ),
                {"id": handoff.handoff_id},
            )
        ).one()
        now = await connection.scalar(text("SELECT clock_timestamp()"))
        # 尝试达 5 次或首次起已超 90 秒，判预算耗尽，置 exhausted 并登记故障，不再接手。
        if attempts[0] >= 5 or (
            attempts[1] is not None and now - attempts[1] >= timedelta(seconds=90)
        ):
            await connection.execute(
                text(
                    "UPDATE runtime.handoffs SET "
                    "state='exhausted',lease_owner=NULL,lease_until=NULL "
                    "WHERE handoff_id=:id"
                ),
                {"id": handoff.handoff_id},
            )
            await mark_failure(connection, handoff, "unknown", "PUBLISH_BUDGET_EXHAUSTED")
            return None
        # 抢占续租约 30 秒，绑定当前持有者。
        updated = (
            (
                await connection.execute(
                    text(
                        "UPDATE runtime.handoffs SET state='leased',lease_owner=:owner,"
                        "lease_until=clock_timestamp()+interval '30 seconds' WHERE "
                        "handoff_id=:id RETURNING *"
                    ),
                    {"id": handoff.handoff_id, "owner": owner},
                )
            )
            .mappings()
            .one()
        )
        # 本次尝试序号取已有次数加一；先落一条 outcome=unknown 的尝试记录，结果待 finish 回填。
        attempt_no = attempts[0] + 1
        await connection.execute(
            text(
                "INSERT INTO runtime.handoff_attempts(handoff_id,attempt_no,started_at,outcome) "
                "VALUES (:id,:attempt,clock_timestamp(),'unknown')"
            ),
            {"id": handoff.handoff_id, "attempt": attempt_no},
        )
        # 租约截止按首次尝试起算的 90 秒总预算，而非每次续租重新计时。
        return Lease(
            Handoff.model_validate_json(json.dumps(dict(updated), default=str)),
            attempt_no,
            owner,
            (attempts[1] or now) + timedelta(seconds=90),
        )


async def finish(
    engine: AsyncEngine,
    lease: Lease,
    *,
    stream: str | None = None,
    sequence: int | None = None,
    error_code: str | None = None,
) -> bool:
    """只允许当前租约落定；晚到确认不能覆盖后来持有者。"""
    async with engine.begin() as connection:
        # 加行锁核对归属：只有仍是 leased、当前持有者且租约未过期，才允许本次落定。
        current = (
            await connection.execute(
                text(
                    "SELECT state,lease_owner,lease_until>clock_timestamp() FROM runtime.handoffs "
                    "WHERE handoff_id=:id FOR UPDATE"
                ),
                {"id": lease.handoff.handoff_id},
            )
        ).one()
        if current != ("leased", lease.owner, True):
            return False
        # 同时带回流名与序号才算发布成功；否则结果未知，进入退避重投。
        success = stream is not None and sequence is not None
        # 退避间隔按尝试次数递增，封顶 20 秒。
        delay = (2, 5, 10, 20, 20)[lease.attempt_no - 1]
        # 回填本次尝试结果；仅更新尚未收尾的记录，防止晚到回执覆盖新尝试。
        await connection.execute(
            text(
                "UPDATE runtime.handoff_attempts SET "
                "finished_at=clock_timestamp(),outcome=:outcome,"
                "error=CAST(:error AS jsonb),transport_receipt=CAST(:receipt AS jsonb) "
                "WHERE handoff_id=:id AND attempt_no=:attempt AND finished_at IS NULL"
            ),
            {
                "id": lease.handoff.handoff_id,
                "attempt": lease.attempt_no,
                "outcome": "delivered" if success else "unknown",
                "error": json.dumps(
                    {"code": error_code or "PUBLISH_UNKNOWN", "message": "发布未获确认"}
                )
                if not success
                else None,
                "receipt": Ref(
                    owner="runtime", type="nats_message", id=f"{stream}:{sequence}"
                ).model_dump_json()
                if success
                else None,
            },
        )
        # 交接落定：成功置 delivered，失败回 pending 并按退避间隔排下次重投；释放租约。
        await connection.execute(
            text(
                "UPDATE runtime.handoffs SET state=:state,lease_owner=NULL,lease_until=NULL,"
                "next_attempt_at=clock_timestamp()+make_interval(secs=>:delay),"
                "stream_name=:stream,stream_sequence=:sequence WHERE handoff_id=:id"
            ),
            {
                "id": lease.handoff.handoff_id,
                "state": "delivered" if success else "pending",
                "delay": delay,
                "stream": stream,
                "sequence": sequence,
            },
        )
        return True


async def mark_failure(
    connection: AsyncConnection,
    handoff: Handoff,
    kind: str,
    reason: str,
    *,
    subscriber: str | None = None,
    basis: Ref | None = None,
    commit_id: UUID | None = None,
) -> None:
    """相同故障只登记一次；保留未知结果，不把未收到通知误判为业务失败。"""
    changed = False
    # 逐个订阅者登记故障：指定了订阅者只记该方，否则快照内全部记。
    for subscriber_id in [subscriber] if subscriber else handoff.subscription_snapshot:
        identity = uuid4()
        # 同一交接+订阅者+故障类型重复登记时忽略，保证故障行只落一次。
        result = await connection.execute(
            text(
                "INSERT INTO runtime.delivery_failures "
                "(failure_id,handoff_id,event_id,subscriber_id,failure_kind,"
                "state,basis_refs,created_at,updated_at) "
                "VALUES (:id,:handoff,:event,:subscriber,:kind,'needs_check',CAST(:basis AS jsonb),"
                "clock_timestamp(),clock_timestamp()) ON CONFLICT DO NOTHING RETURNING failure_id"
            ),
            {
                "id": identity,
                "handoff": handoff.handoff_id,
                "event": handoff.payload.event_id,
                "subscriber": subscriber_id,
                "kind": kind,
                "basis": json.dumps([basis.model_dump(mode="json")] if basis else []),
            },
        )
        # 确认为新增故障行才回写交接的最近故障引用；冲突忽略的重复行不覆盖。
        if result.scalar_one_or_none() is not None:
            changed = True
            await connection.execute(
                text(
                    "UPDATE runtime.handoffs SET last_failure_ref=CAST(:failure AS jsonb) "
                    "WHERE handoff_id=:id"
                ),
                {
                    "id": handoff.handoff_id,
                    "failure": Ref(
                        owner="runtime", type="delivery_failure", id=str(identity)
                    ).model_dump_json(),
                },
            )
    # 至少新增一条故障行才留痕；全为重复登记时不产生变更事件。
    if changed:
        await record_change(
            connection, handoff.handoff_id, "failed", reason_code=reason, commit_id=commit_id
        )
