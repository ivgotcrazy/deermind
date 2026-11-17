"""通知、收据与技术传输合同；不包含订阅处理实现。"""

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import Field, model_validator

from deermind.abstractions.events import FactModel, NonEmpty, Ref

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


@dataclass(frozen=True)
class SubscriptionSpec:
    subscriber_id: str
    revision: str
    event_types: frozenset[str]
    scope_kinds: frozenset[str]


class DeliveryUnavailable(LookupError):
    """已登记的技术订阅或消息不存在。"""


class IncomingMessage(Protocol):
    @property
    def data(self) -> bytes: ...
    @property
    def subject(self) -> str: ...
    async def retry(self) -> None: ...
    async def reject(self) -> None: ...
    async def acknowledge(self) -> None: ...


@dataclass(frozen=True)
class DeliveryAdvisory:
    stream: str
    sequence: int
    subscriber: str
    kind: Literal["delivery_exhausted", "rejected"]
    reference: Ref


class MessageTransport(Protocol):
    async def check_subscribers(self, subscriptions: Sequence[SubscriptionSpec]) -> None: ...
    async def publish(self, notice: EventNotice) -> tuple[str, int]: ...
    def receive(
        self, subscriber: str, *, failure: bool = False
    ) -> AbstractAsyncContextManager[IncomingMessage | None]: ...
    def matches(self, message: IncomingMessage, event_type: str) -> bool: ...
    def advisory(self, message: IncomingMessage) -> DeliveryAdvisory: ...
    async def delivery_status(
        self, subscriber: str, sequence: int | None
    ) -> Literal["unknown", "consumer_missing", "transport_lost"]: ...
