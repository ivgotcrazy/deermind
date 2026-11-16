"""发布安排、短租约和重试预算；远程发布始终在事务外执行。"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from deermind.foundation.system.delivery.contracts import EventNotice, Handoff, SubscriptionRegistry
from deermind.foundation.system.delivery.facts import record_change
from deermind.foundation.system.events.contracts import Ref, StoredEvent
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


@dataclass(frozen=True)
class Lease:
    handoff: Handoff
    attempt_no: int
    owner: str
    deadline: datetime


class Outbox:
    """固定应接收方后再交接；无订阅的审计事实仅保存在数据库。"""

    def __init__(self, registry: SubscriptionRegistry) -> None:
        self.registry = registry

    async def arrange(self, connection: AsyncConnection, event: StoredEvent) -> None:
        subscribers = self.registry.matching(event.draft.event_type, event.draft.scope_kind)
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
        if row is None:
            return None
        handoff = Handoff.model_validate_json(json.dumps(dict(row), default=str))
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
        attempt_no = attempts[0] + 1
        await connection.execute(
            text(
                "INSERT INTO runtime.handoff_attempts(handoff_id,attempt_no,started_at,outcome) "
                "VALUES (:id,:attempt,clock_timestamp(),'unknown')"
            ),
            {"id": handoff.handoff_id, "attempt": attempt_no},
        )
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
        success = stream is not None and sequence is not None
        delay = (2, 5, 10, 20, 20)[lease.attempt_no - 1]
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
    for subscriber_id in [subscriber] if subscriber else handoff.subscription_snapshot:
        identity = uuid4()
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
    if changed:
        await record_change(
            connection, handoff.handoff_id, "failed", reason_code=reason, commit_id=commit_id
        )
