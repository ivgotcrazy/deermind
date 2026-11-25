"""通知、收据与技术传输合同；不包含订阅处理实现。

分层定位：abstractions（跨层合同）
对外契约：DeliveryNotice、EventNotice、Acceptance、Handoff、SubscriptionReceipt、
DeliveryFailure 及消息传输端口 Protocol。
边界约束：只定义交接安排、回执与传输接口，不含订阅匹配与重试投递实现。
"""

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
        # 仅被拒绝的回执可带错误，其余处置不得夹带错误信息。
        if (self.disposition == "rejected") != (self.error is not None):
            raise ValueError("Only rejected receipts must contain an error")
        # 已受理必须附带已保存的安排引用，不能空受理。
        if self.disposition == "accepted" and not self.arrangement_refs:
            raise ValueError("Acceptance requires a saved arrangement")
        return self


class Handoff(FactModel):
    """一次事件交接安排：投递状态、租约归属、订阅快照与流位置。"""

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
    """一次投递尝试的结果、错误与传输回执。"""

    handoff_id: UUID
    attempt_no: int
    started_at: datetime
    finished_at: datetime | None
    outcome: Literal["delivered", "failed", "unknown"]
    error: dict[str, str] | None
    transport_receipt: Ref | None


class SubscriptionReceipt(FactModel):
    """某订阅者对事件的接收回执：处置结论、已保存安排引用与错误。"""

    subscriber_id: str
    event_id: UUID
    handler_revision: str
    disposition: Literal["accepted", "rejected", "ignored"]
    arrangement_refs: list[Ref]
    error: dict[str, str] | None
    created_at: datetime


class DeliveryFailure(FactModel):
    """交接失败记录：失败类别、处置状态、依据引用与恢复引用。"""

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
    """订阅者登记：身份、处理器版本与订阅的事件类型、范围种类集合。"""

    subscriber_id: str
    revision: str
    event_types: frozenset[str]
    scope_kinds: frozenset[str]


class DeliveryUnavailable(LookupError):
    """已登记的技术订阅或消息不存在。"""


class IncomingMessage(Protocol):
    """传输层收到的入站消息端口：读取载荷与主题，决定重试、拒绝或确认。"""

    @property
    def data(self) -> bytes: ...
    @property
    def subject(self) -> str: ...
    async def retry(self) -> None: ...
    async def reject(self) -> None: ...
    async def acknowledge(self) -> None: ...


@dataclass(frozen=True)
class DeliveryAdvisory:
    """传输层给出的失败/耗尽提示定位：流、序号、订阅者、类别与依据引用。"""

    stream: str
    sequence: int
    subscriber: str
    kind: Literal["delivery_exhausted", "rejected"]
    reference: Ref


class MessageTransport(Protocol):
    """消息中间件端口：登记订阅、发布通知、接收消息、类型匹配与投递状态查询。"""

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
