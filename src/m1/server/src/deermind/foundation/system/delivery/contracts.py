"""进程内订阅合同及严格通知格式；通知不携带正文或读取授权。"""

import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from deermind.foundation.system.events.contracts import FactModel, NonEmpty, Ref
from pydantic import Field, model_validator
from sqlalchemy.ext.asyncio import AsyncConnection

Name = Annotated[str, Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")]


class DeliveryNotice(FactModel):
    """引用必须与库中事件及交接安排一致，不能把外部通知当作事实。"""

    delivery_id: UUID
    event_id: UUID
    event_type: Name
    schema_version: Annotated[int, Field(ge=1)]
    producer: NonEmpty
    scope_kind: NonEmpty
    scope_id: UUID


class EventNotice(DeliveryNotice):
    """内部安排另存handoff_id；传输副本只使用DeliveryNotice字段。"""

    handoff_id: UUID


class Acceptance(FactModel):
    """回调在同一事务内保存安排，返回其引用；不允许在回调内执行远程工作。"""

    disposition: Literal["accepted", "rejected", "ignored"]
    arrangement_refs: list[Ref]
    error: dict[str, str] | None = None

    @model_validator(mode="after")
    def check_result(self) -> "Acceptance":
        if (self.disposition == "rejected") != (self.error is not None):
            raise ValueError("Only rejected receipts must contain an error")
        if self.disposition == "accepted" and not self.arrangement_refs:
            raise ValueError("Acceptance requires a saved arrangement")
        return self


@dataclass(frozen=True)
class Subscription:
    """仅装配层注册，M1业务从新事件开始；历史补送由单独维护授权决定。"""

    subscriber_id: str
    revision: str
    event_types: frozenset[str]
    scope_kinds: frozenset[str]
    accept: Callable[[AsyncConnection, EventNotice], Awaitable[Acceptance]]


class SubscriptionRegistry:
    """固定订阅快照；禁止投递留痕订阅自己，避免无限事件循环。"""

    def __init__(self, subscriptions: Sequence[Subscription]) -> None:
        self.items = tuple(subscriptions)
        names: set[str] = set()
        for item in self.items:
            if (
                item.subscriber_id in names
                or not item.revision
                or not item.event_types
                or not item.scope_kinds
                or "DeliveryStateChanged" in item.event_types
                or not callable(item.accept)
                or any(
                    re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name) is None
                    for name in (item.subscriber_id, *item.event_types, *item.scope_kinds)
                )
            ):
                raise ValueError("Invalid or duplicate subscription")
            names.add(item.subscriber_id)

    def matching(self, event_type: str, scope_kind: str) -> list[Subscription]:
        return [
            item
            for item in self.items
            if event_type in item.event_types and scope_kind in item.scope_kinds
        ]


class Handoff(FactModel):
    handoff_id: UUID
    kind: Literal["publish", "start", "signal", "cancel"]
    logical_key: NonEmpty
    source_ref: Ref
    payload: EventNotice
    state: Literal["pending", "leased", "delivered", "exhausted"]
    next_attempt_at: datetime
    lease_owner: str | None
    lease_until: datetime | None
    subscription_snapshot: dict[str, str]
    delivery_id: UUID
    stream_name: str | None
    stream_sequence: int | None
    authorization_ref: Ref | None
    last_failure_ref: Ref | None
    created_at: datetime


class HandoffAttempt(FactModel):
    handoff_id: UUID
    attempt_no: int
    started_at: datetime
    finished_at: datetime | None
    outcome: Literal["delivered", "failed", "unknown"]
    error: dict[str, str] | None
    transport_receipt: Ref | None


class SubscriptionReceipt(FactModel):
    subscriber_id: str
    event_id: UUID
    handler_revision: str
    disposition: Literal["accepted", "rejected", "ignored"]
    arrangement_refs: list[Ref]
    error: dict[str, str] | None
    created_at: datetime


class DeliveryFailure(FactModel):
    failure_id: UUID
    handoff_id: UUID
    event_id: UUID
    subscriber_id: str
    failure_kind: Literal[
        "delivery_exhausted", "consumer_missing", "transport_lost", "rejected", "unknown"
    ]
    state: Literal["needs_check", "confirmed", "resolved"]
    basis_refs: list[Ref]
    recovery_ref: Ref | None
    created_at: datetime
    updated_at: datetime
