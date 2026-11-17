"""Worker中的发布与订阅桥；失败留在交接层，不调用AI或重跑业务。"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from deermind.abstractions.delivery import (
    DeliveryNotice,
    DeliveryUnavailable,
    Handoff,
    MessageTransport,
    SubscriptionSpec,
)
from deermind.foundation.system.delivery.consumer import accept
from deermind.foundation.system.delivery.contracts import Subscription, SubscriptionRegistry
from deermind.foundation.system.delivery.outbox import claim, finish, mark_failure
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

LOGGER = logging.getLogger("runtime")


async def publish_one(
    engine: AsyncEngine, transport: MessageTransport, registry: SubscriptionRegistry
) -> bool:
    """无工作返回False；失联结果未知时使用同一投递身份补发。"""
    lease = await claim(engine, str(uuid4()))
    if lease is None:
        return False
    try:
        remaining = (lease.deadline - datetime.now(UTC)).total_seconds()
        async with asyncio.timeout(min(5, max(0, remaining))):
            registered = {
                item.subscriber_id: item
                for item in registry.matching(
                    lease.handoff.payload.event_type, lease.handoff.payload.scope_kind
                )
            }
            required: list[SubscriptionSpec] = []
            for name, revision in lease.handoff.subscription_snapshot.items():
                item = registered.get(name)
                if item is None or item.revision != revision:
                    raise ValueError("Expected subscriber is not registered")
                required.append(
                    SubscriptionSpec(
                        item.subscriber_id, item.revision, item.event_types, item.scope_kinds
                    )
                )
            await transport.check_subscribers(required)
            stream, sequence = await transport.publish(lease.handoff.payload)
    except Exception as error:
        code = (
            "SUBSCRIBER_UNAVAILABLE"
            if isinstance(error, (ValueError, DeliveryUnavailable))
            else "PUBLISH_UNKNOWN"
        )
        current = await finish(engine, lease, error_code=code)
        if current and code == "SUBSCRIBER_UNAVAILABLE":
            async with engine.begin() as connection:
                await connection.execute(
                    text("SELECT handoff_id FROM runtime.handoffs WHERE handoff_id=:id FOR UPDATE"),
                    {"id": lease.handoff.handoff_id},
                )
                await mark_failure(connection, lease.handoff, "consumer_missing", code)
        LOGGER.warning(
            "事件尚未确认发布，已保留原安排",
            extra={
                "action": "event_publish",
                "outcome": "pending",
                "error_code": code,
                "event_id": str(lease.handoff.payload.event_id),
            },
        )
    else:
        await finish(engine, lease, stream=stream, sequence=sequence)
        LOGGER.info(
            "事件已交给消息队列",
            extra={
                "action": "event_publish",
                "outcome": "success",
                "event_id": str(lease.handoff.payload.event_id),
            },
        )
    return True


async def consume_one(
    engine: AsyncEngine, transport: MessageTransport, subscription: Subscription
) -> bool:
    """收据提交后Ack；处理失败仅延期投递，不把队列当作业务重试器。"""
    async with transport.receive(subscription.subscriber_id) as message:
        if message is None:
            return False
        try:
            if len(message.data) > 64 * 1024:
                raise ValueError("Event notice exceeds 64KiB")
            notice = DeliveryNotice.model_validate_json(message.data)
            if not transport.matches(message, notice.event_type):
                raise ValueError("Notification subject mismatch")
            receipt = await accept(engine, subscription, notice)
        except Exception:
            LOGGER.exception(
                "事件承接未提交，将按交接上限重投",
                extra={
                    "action": "event_accept",
                    "outcome": "failed",
                    "error_code": "ACCEPT_NOT_COMMITTED",
                },
            )
            await message.retry()
            return True
        if receipt.disposition == "rejected":
            await message.reject()
        else:
            await message.acknowledge()
        LOGGER.info(
            "事件承接已保存并确认",
            extra={
                "action": "event_accept",
                "outcome": "rejected" if receipt.disposition == "rejected" else "success",
                "event_id": str(notice.event_id),
                "subscriber_id": subscription.subscriber_id,
                **(
                    {"error_code": "SUBSCRIBER_REJECTED"}
                    if receipt.disposition == "rejected"
                    else {}
                ),
            },
        )
        return True


async def collect_one(engine: AsyncEngine, transport: MessageTransport) -> bool:
    """未能关联的失败通知留在队列；故障行保存后才确认收到。"""
    async with transport.receive("failure_collector", failure=True) as message:
        if message is None:
            return False
        advisory = transport.advisory(message)
        stream, sequence, subscriber = advisory.stream, advisory.sequence, advisory.subscriber
        async with engine.begin() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT * FROM runtime.handoffs WHERE kind='publish' AND "
                            "stream_name=:stream "
                            "AND stream_sequence=:seq FOR UPDATE"
                        ),
                        {"stream": stream, "seq": sequence},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                # 发布成功但确认尚未落库时等待补发落定，不凭通知猜事件身份。
                await message.retry()
                return True
            handoff = Handoff.model_validate_json(json.dumps(dict(row), default=str))
            if subscriber not in handoff.subscription_snapshot:
                raise ValueError("Advisory subscriber not in the saved snapshot")
            receipt = await connection.scalar(
                text(
                    "SELECT disposition FROM runtime.subscription_receipts WHERE "
                    "subscriber_id=:subscriber AND event_id=:event"
                ),
                {"subscriber": subscriber, "event": handoff.payload.event_id},
            )
            if receipt is None:
                kind = advisory.kind
                await mark_failure(
                    connection,
                    handoff,
                    kind,
                    "DELIVERY_ADVISORY",
                    subscriber=subscriber,
                    basis=advisory.reference,
                )
        await message.acknowledge()
        return True


async def reconcile(engine: AsyncEngine, transport: MessageTransport) -> None:
    """查收据及消息元数据，发现未接住的情况留痕；不擅自补送业务。"""
    async with engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    text(
                        "SELECT h.* FROM runtime.handoffs h WHERE h.kind='publish' AND "
                        "h.state='delivered' "
                        "AND EXISTS (SELECT 1 FROM runtime.handoff_attempts a "
                        "WHERE a.handoff_id=h.handoff_id AND a.outcome='delivered' "
                        "AND a.finished_at < clock_timestamp()-interval '150 seconds') "
                        "AND EXISTS (SELECT 1 FROM "
                        "jsonb_object_keys(h.subscription_snapshot) s(id) "
                        "WHERE NOT EXISTS (SELECT 1 FROM runtime.subscription_receipts r "
                        "WHERE r.event_id=CAST(h.payload->>'event_id' AS uuid) AND "
                        "r.subscriber_id=s.id) AND NOT EXISTS "
                        "(SELECT 1 FROM runtime.delivery_failures f "
                        "WHERE f.handoff_id=h.handoff_id "
                        "AND f.subscriber_id=s.id)) "
                        "ORDER BY h.created_at LIMIT 100"
                    )
                )
            )
            .mappings()
            .all()
        )
    for row in rows:
        handoff = Handoff.model_validate_json(json.dumps(dict(row), default=str))
        for subscriber in handoff.subscription_snapshot:
            kind = await transport.delivery_status(subscriber, handoff.stream_sequence)
            async with engine.begin() as connection:
                await connection.execute(
                    text("SELECT handoff_id FROM runtime.handoffs WHERE handoff_id=:id FOR UPDATE"),
                    {"id": handoff.handoff_id},
                )
                receipt = await connection.scalar(
                    text(
                        "SELECT disposition FROM runtime.subscription_receipts WHERE "
                        "event_id=:event AND subscriber_id=:subscriber"
                    ),
                    {"event": handoff.payload.event_id, "subscriber": subscriber},
                )
                if receipt is None:
                    await mark_failure(
                        connection, handoff, kind, "RECEIPT_NOT_FOUND", subscriber=subscriber
                    )


async def run_bridge(
    engine: AsyncEngine,
    transport: MessageTransport,
    registry: SubscriptionRegistry,
    stopped: asyncio.Event,
) -> None:
    """共享Worker内独立轮询；取消退出不删除未完成安排。"""

    async def publisher() -> None:
        while not stopped.is_set():
            try:
                await publish_one(engine, transport, registry)
            except Exception:
                LOGGER.exception(
                    "发布循环暂不可用，已保存工作不会丢弃",
                    extra={"action": "publisher", "outcome": "failed"},
                )
            await asyncio.sleep(1)

    async def subscriber(item: Subscription) -> None:
        while not stopped.is_set():
            try:
                await consume_one(engine, transport, item)
            except Exception:
                LOGGER.exception(
                    "订阅暂不可用，持久消费者保留",
                    extra={"action": "subscriber", "outcome": "failed"},
                )
                await asyncio.sleep(1)

    async def collector() -> None:
        while not stopped.is_set():
            try:
                await collect_one(engine, transport)
            except Exception:
                LOGGER.exception(
                    "失败通知待核对，未确认记录保留",
                    extra={"action": "failure_collector", "outcome": "failed"},
                )
                await asyncio.sleep(1)

    async def checker() -> None:
        while not stopped.is_set():
            try:
                await reconcile(engine, transport)
            except Exception:
                LOGGER.exception(
                    "交接核对暂不可用", extra={"action": "delivery_reconcile", "outcome": "failed"}
                )
            await asyncio.sleep(30)

    tasks = [
        asyncio.create_task(publisher()),
        asyncio.create_task(collector()),
        asyncio.create_task(checker()),
    ]
    tasks.extend(asyncio.create_task(subscriber(item)) for item in registry.items)
    try:
        await stopped.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
