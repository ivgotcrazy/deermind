"""等待与发布结果的数据合同。"""

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, JsonValue

from deermind.abstractions.events import FactModel, NonEmpty, Ref
from deermind.abstractions.executions import RunInput


class ResultKey(FactModel):
    scope_id: UUID
    trigger_event_id: UUID
    producer: NonEmpty
    result_kind: NonEmpty


class Publication(ResultKey):
    execution_id: UUID
    attempt_id: UUID
    result_ref: Ref
    publication_refs: list[Ref]
    payload: dict[str, JsonValue]
    event_id: UUID
    published_at: datetime


class ResultView(FactModel):
    state: Literal["available", "pending", "failed", "not_found"]
    publication: Publication | None = None
    failure_ref: Ref | None = None


class Condition(FactModel):
    """仅固定类型、范围和等值；更复杂业务条件在登记的只读probe中核对。"""

    event_types: list[NonEmpty] = Field(min_length=1)
    scope_kind: NonEmpty
    scope_id: UUID
    equals: dict[str, str] = Field(default_factory=dict)
    result_key: ResultKey | None = None


class Wait(FactModel):
    wait_id: UUID
    owner_ref: Ref
    execution_id: UUID
    step_key: NonEmpty
    condition: Condition
    condition_hash: NonEmpty
    probe_ref: Ref
    deadline_at: datetime
    resume_action_id: UUID
    on_match: NonEmpty
    on_timeout: NonEmpty
    resolution: Literal["pending", "matched", "timed_out", "cancelled"]
    matched_event_ref: UUID | None
    result_ref: Ref | None
    created_at: datetime
    resolved_at: datetime | None


class Handling(FactModel):
    wait_id: UUID
    resume_action_id: UUID
    state: Literal["awaiting", "committed", "failed", "cancelled"]
    handling_receipt_ref: Ref | None
    failure_ref: Ref | None
    updated_at: datetime


class Match(FactModel):
    event_id: UUID
    result_ref: Ref | None


class WaitCall(FactModel):
    run: RunInput
    wait_id: UUID


class WaitService(Protocol):
    async def probe(self, call: WaitCall) -> Wait: ...
    async def handle(self, call: WaitCall) -> Handling: ...
