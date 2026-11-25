"""受控重送只补指定事件尚未承接的订阅；不清除旧收据或改写事实。

分层定位：foundation（公共运行底座 / 事件交接）
对外契约：redeliver 供维护账号对已耗尽/已送达的交接批准受控重送。
边界约束：同一批准号复用安排；自动重试未结束时拒绝；只补失败且未承接的订阅。
"""

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
    # 操作人与批准引用均不能为空。
    if not operator.strip() or not authorization.strip():
        raise ValueError("Operator and approval reference are required")
    async with engine.begin() as connection:
        # 仅维护账号可批准重送，普通订阅方无权触发。
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
        # 同一批准号已有重送安排：幂等返回原交接，不重复建。
        if existing is not None:
            return existing
        # 交接仍在自动重试中，未到耗尽/已送达，不允许手工重送。
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
        # 仅重送“失败过且至今未承接”的订阅；已收到收据的不重复推送。
        expected = {
            name: revision
            for name, revision in previous.subscription_snapshot.items()
            if name in failures and name not in received
        }
        # 没有可重送的订阅，拒绝生成空交接。
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
