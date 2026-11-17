"""受控重送只补指定事件尚未承接的订阅；不清除旧收据或改写事实。"""

import json
from uuid import UUID, uuid4

from deermind.abstractions.delivery import Handoff
from deermind.abstractions.events import Ref
from deermind.foundation.system.delivery.facts import record_change
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def redeliver(
    engine: AsyncEngine,
    handoff_id: UUID,
    *,
    operator: str,
    authorization: str,
) -> UUID:
    """仅维护账号可调用；同一批准号复用安排，自动重试未结束时拒绝重送。"""
    if not operator.strip() or not authorization.strip():
        raise ValueError("Operator and approval reference are required")
    async with engine.begin() as connection:
        if await connection.scalar(text("SELECT current_user")) != "deermind_migrator":
            raise PermissionError("Redelivery requires maintenance credentials")
        row = (
            (
                await connection.execute(
                    text("SELECT * FROM runtime.handoffs WHERE handoff_id=:id FOR UPDATE"),
                    {"id": handoff_id},
                )
            )
            .mappings()
            .one()
        )
        previous = Handoff.model_validate_json(json.dumps(dict(row), default=str))
        key = f"{previous.payload.event_id}:approved:{authorization}"
        existing = await connection.scalar(
            text(
                "SELECT handoff_id FROM runtime.handoffs WHERE kind='publish' AND logical_key=:key"
            ),
            {"key": key},
        )
        if existing is not None:
            return existing
        if previous.state not in {"exhausted", "delivered"}:
            raise ValueError("Automatic delivery is still active")
        failures = set(
            await connection.scalars(
                text("SELECT subscriber_id FROM runtime.delivery_failures WHERE handoff_id=:id"),
                {"id": handoff_id},
            )
        )
        received = set(
            await connection.scalars(
                text(
                    "SELECT subscriber_id FROM runtime.subscription_receipts WHERE event_id=:event"
                ),
                {"event": previous.payload.event_id},
            )
        )
        expected = {
            name: revision
            for name, revision in previous.subscription_snapshot.items()
            if name in failures and name not in received
        }
        if not expected:
            raise ValueError("No unaccepted failed subscription to redeliver")
        identity, delivery_id, commit_id = uuid4(), uuid4(), uuid4()
        notice = previous.payload.model_copy(
            update={"handoff_id": identity, "delivery_id": delivery_id}
        )
        approval = Ref(owner="runtime", type="maintenance_approval", id=authorization)
        actor = Ref(owner="runtime", type="operator", id=operator)
        await connection.execute(
            text(
                "INSERT INTO runtime.handoffs "
                "(handoff_id,kind,logical_key,source_ref,payload,state,next_attempt_at,"
                "subscription_snapshot,delivery_id,authorization_ref,created_at) VALUES "
                "(:id,'publish',:key,CAST(:source AS jsonb),CAST(:payload AS jsonb),'pending',"
                "clock_timestamp(),CAST(:expected AS jsonb),:delivery,"
                "CAST(:approval AS jsonb),clock_timestamp())"
            ),
            {
                "id": identity,
                "key": key,
                "source": previous.source_ref.model_dump_json(),
                "payload": notice.model_dump_json(),
                "expected": json.dumps(expected),
                "delivery": delivery_id,
                "approval": approval.model_dump_json(),
            },
        )
        await connection.execute(
            text(
                "UPDATE runtime.delivery_failures SET state='confirmed',"
                "recovery_ref=CAST(:ref AS jsonb),"
                "updated_at=clock_timestamp() WHERE handoff_id=:id "
                "AND subscriber_id=ANY(:subscribers)"
            ),
            {
                "id": handoff_id,
                "subscribers": list(expected),
                "ref": Ref(owner="runtime", type="handoff", id=str(identity)).model_dump_json(),
            },
        )
        await record_change(
            connection, handoff_id, "redelivery_approved", commit_id=commit_id, actor_ref=actor
        )
        await record_change(connection, identity, "arranged", commit_id=commit_id, actor_ref=actor)
        return identity
