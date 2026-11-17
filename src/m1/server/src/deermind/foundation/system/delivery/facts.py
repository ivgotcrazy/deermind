"""交接关键结论追加为事实；租约、轮询和网络心跳不生成事实。"""

import json
from typing import Literal
from uuid import UUID, uuid4

from deermind.abstractions.delivery import (
    DeliveryFailure,
    Handoff,
    HandoffAttempt,
    SubscriptionReceipt,
)
from deermind.abstractions.event_reading import (
    EventFact,
    EventPartRef,
    ReadAccess,
    ReadGrant,
    ReadPolicy,
)
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    FactRecord,
    InlineContent,
    ProducerAccess,
    Ref,
)
from deermind.foundation.system.events.store import EventStore
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

Outcome = Literal["arranged", "accepted", "rejected", "ignored", "failed", "redelivery_approved"]
MODELS: dict[str, type[FactModel]] = {
    "runtime.handoffs": Handoff,
    "runtime.handoff_attempts": HandoffAttempt,
    "runtime.subscription_receipts": SubscriptionReceipt,
    "runtime.delivery_failures": DeliveryFailure,
}


class DeliveryStateChanged(EventPayload):
    subject_ref: Ref
    outcome: Outcome
    reason_code: str | None
    source_event_ref: EventPartRef


def validate_delivery(draft: EventDraft, payload: EventPayload) -> None:
    """只接受完整控制记录；同名H记录不取得重建业务表的权限。"""
    if not isinstance(payload, DeliveryStateChanged) or payload.subject_ref != draft.owner_ref:
        raise ValueError("Invalid delivery fact identity")
    counts: dict[str, int] = {}
    for record in payload.records:
        model = MODELS.get(record.record_type)
        if (
            model is None
            or record.schema_version != 1
            or not isinstance(record.content, InlineContent)
        ):
            raise ValueError("Invalid delivery fact record")
        item = model.model_validate_json(json.dumps(record.content.value))
        if isinstance(item, Handoff) and (
            item.handoff_id != draft.scope_id
            or item.payload.event_id != payload.source_event_ref.event_id
        ):
            raise ValueError("Delivery fact source differs from its handoff")
        counts[record.record_type] = counts.get(record.record_type, 0) + 1
    if counts.get("runtime.handoffs") != 1:
        raise ValueError("Delivery fact requires exactly one handoff")
    if (
        payload.outcome in {"accepted", "rejected", "ignored"}
        and counts.get("runtime.subscription_receipts") != 1
    ):
        raise ValueError("Acceptance fact requires a receipt")


DELIVERY_REGISTRATION = EventRegistration(
    "DeliveryStateChanged",
    1,
    "runtime",
    "event_delivery",
    DeliveryStateChanged,
    validate_delivery,
    {(name, 1): model for name, model in MODELS.items()},
)


async def record_change(
    connection: AsyncConnection,
    handoff_id: UUID,
    outcome: Outcome,
    *,
    subscriber_id: str | None = None,
    reason_code: str | None = None,
    commit_id: UUID | None = None,
    actor_ref: Ref | None = None,
) -> None:
    """持有交接行锁时调用；与交接状态或收据同提交，不安排自身发布。"""
    handoff = (
        (
            await connection.execute(
                text("SELECT * FROM runtime.handoffs WHERE handoff_id=:id"), {"id": handoff_id}
            )
        )
        .mappings()
        .one()
    )
    event_id = UUID(handoff["payload"]["event_id"])
    records: list[FactRecord] = []

    def add(table: str, row: object, identity: str) -> None:
        # DB边界的UUID/时间转为JSON，再按固定DTO严格校验。
        content = MODELS[table].model_validate_json(json.dumps(row, default=str))
        records.append(
            FactRecord(
                record_id=identity,
                record_type=table,
                schema_version=1,
                content=InlineContent(storage="inline", value=content.model_dump(mode="json")),
            )
        )

    add("runtime.handoffs", dict(handoff), "handoff")
    if subscriber_id is not None:
        receipt = (
            (
                await connection.execute(
                    text(
                        "SELECT * FROM runtime.subscription_receipts "
                        "WHERE subscriber_id=:subscriber AND event_id=:event"
                    ),
                    {"subscriber": subscriber_id, "event": event_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if receipt is not None:
            add("runtime.subscription_receipts", dict(receipt), "receipt")
    failures = (
        await connection.execute(
            text(
                "SELECT * FROM runtime.delivery_failures WHERE handoff_id=:id ORDER BY failure_id"
            ),
            {"id": handoff_id},
        )
    ).mappings()
    for failure in failures:
        add("runtime.delivery_failures", dict(failure), str(failure["failure_id"]))

    owner = Ref(owner="runtime", type="handoff", id=str(handoff_id))
    payload = DeliveryStateChanged(
        subject_ref=owner,
        outcome=outcome,
        reason_code=reason_code,
        records=records,
        source_event_ref=EventPartRef(event_id=event_id, record_id=None, path=""),
    )
    scope = ("event_delivery", handoff_id)
    sequence = await connection.scalar(
        text(
            "SELECT last_seq FROM runtime.scope_event_heads WHERE scope_kind=:kind AND scope_id=:id"
        ),
        {"kind": scope[0], "id": handoff_id},
    )
    await EventStore([DELIVERY_REGISTRATION]).append(
        connection,
        ProducerAccess(
            "runtime",
            actor_ref or Ref(owner="runtime", type="service", id="delivery"),
            frozenset({scope}),
            frozenset({event_id}),
        ),
        [
            EventDraft(
                uuid4(),
                "DeliveryStateChanged",
                1,
                *scope,
                owner,
                payload.model_dump(mode="json"),
                None,
                causation_event_id=event_id,
                subject_refs=(
                    Ref(
                        owner=handoff["payload"]["producer"],
                        type=handoff["payload"]["scope_kind"],
                        id=handoff["payload"]["scope_id"],
                    ),
                ),
            )
        ],
        commit_id=commit_id or uuid4(),
        correlation_id=event_id,
        expected_seq={scope: sequence or 0},
    )


def maintenance_grant(access: ReadAccess, event: EventFact) -> ReadGrant | None:
    if access.maintenance_ref is None:
        return None
    return ReadGrant(
        {(name, 1): None for name in MODELS},
        frozenset({"subject_ref", "outcome", "reason_code", "source_event_ref"}),
        "事件交接记录",
    )


DELIVERY_READ_POLICY = ReadPolicy(
    "DeliveryStateChanged",
    1,
    "runtime",
    "execution_support",
    maintenance_grant,
)
