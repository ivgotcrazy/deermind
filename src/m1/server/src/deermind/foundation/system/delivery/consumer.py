"""订阅方可靠承接；提交后的收据决定是否Ack，后续执行不占消息确认期限。"""

import asyncio
import json
from uuid import uuid4

from deermind.foundation.system.delivery.contracts import (
    Acceptance,
    DeliveryNotice,
    Handoff,
    Subscription,
    SubscriptionReceipt,
)
from deermind.foundation.system.delivery.facts import record_change
from deermind.foundation.system.delivery.outbox import mark_failure
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def accept(
    engine: AsyncEngine,
    subscription: Subscription,
    notice: DeliveryNotice,
) -> SubscriptionReceipt:
    """仅信任库中事实；同订阅同事件串行承接，回调失败则安排和收据全部回滚。"""
    async with asyncio.timeout(20), engine.begin() as connection:
        await connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {
                "key": f"subscription:{subscription.subscriber_id}:{notice.event_id}",
            },
        )
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT * FROM runtime.handoffs WHERE kind='publish' "
                        "AND delivery_id=:id FOR UPDATE"
                    ),
                    {"id": notice.delivery_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ValueError("Notification has no committed handoff")
        handoff = Handoff.model_validate_json(json.dumps(dict(row), default=str))
        if handoff.payload.model_dump(exclude={"handoff_id"}) != notice.model_dump(
            exclude={"handoff_id"}
        ):
            raise PermissionError("Notification does not match its saved subscription")
        source = (
            await connection.execute(
                text(
                    "SELECT event_type,schema_version,scope_kind,scope_id,producer FROM "
                    "runtime.events WHERE event_id=:id"
                ),
                {"id": notice.event_id},
            )
        ).one()
        if source != (
            notice.event_type,
            notice.schema_version,
            notice.scope_kind,
            notice.scope_id,
            notice.producer,
        ):
            raise ValueError("Notification differs from the saved event")
        if notice.event_type not in subscription.event_types:
            raise PermissionError("Subscription does not accept this event type")

        parameters = {"subscriber": subscription.subscriber_id, "event": notice.event_id}
        existing = (
            (
                await connection.execute(
                    text(
                        "SELECT * FROM runtime.subscription_receipts WHERE "
                        "subscriber_id=:subscriber AND event_id=:event"
                    ),
                    parameters,
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            return SubscriptionReceipt.model_validate_json(json.dumps(dict(existing), default=str))
        expected_revision = handoff.subscription_snapshot.get(subscription.subscriber_id)
        if expected_revision is not None and expected_revision != subscription.revision:
            raise ValueError("Subscription revision changed; resolve the saved handoff first")

        # Broker按类型过滤；范围不符或晚加入的订阅只留忽略收据，不调用业务。
        if expected_revision is None or notice.scope_kind not in subscription.scope_kinds:
            result = Acceptance(disposition="ignored", arrangement_refs=[])
        else:
            result = await subscription.accept(connection, handoff.payload)
        saved = (
            (
                await connection.execute(
                    text(
                        "INSERT INTO runtime.subscription_receipts "
                        "(subscriber_id,event_id,handler_revision,disposition,"
                        "arrangement_refs,error,created_at) "
                        "VALUES (:subscriber,:event,:revision,:disposition,CAST(:refs AS "
                        "jsonb),CAST(:error AS jsonb),"
                        "clock_timestamp()) RETURNING *"
                    ),
                    {
                        **parameters,
                        "revision": subscription.revision,
                        "disposition": result.disposition,
                        "refs": json.dumps(
                            [ref.model_dump(mode="json") for ref in result.arrangement_refs]
                        ),
                        "error": json.dumps(result.error) if result.error is not None else None,
                    },
                )
            )
            .mappings()
            .one()
        )
        commit_id = uuid4()
        if result.disposition == "rejected":
            await mark_failure(
                connection,
                handoff,
                "rejected",
                "SUBSCRIBER_REJECTED",
                subscriber=subscription.subscriber_id,
                commit_id=commit_id,
            )
        await record_change(
            connection,
            handoff.handoff_id,
            result.disposition,
            subscriber_id=subscription.subscriber_id,
            commit_id=commit_id,
        )
        return SubscriptionReceipt.model_validate_json(json.dumps(dict(saved), default=str))
