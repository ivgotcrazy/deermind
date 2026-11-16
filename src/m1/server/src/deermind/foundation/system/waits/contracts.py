"""等待、结果及程序登记；消息只唤醒，不能携带回调或扩大读取范围。"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from deermind.foundation.system.events.contracts import FactModel, NonEmpty, Ref
from deermind.foundation.system.executions.contracts import Execution, RunInput
from pydantic import Field, JsonValue
from sqlalchemy.ext.asyncio import AsyncConnection


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


@dataclass(frozen=True)
class Policy:
    """所有者登记只读probe和同事务接续；两者都不调用AI或远程服务。"""

    ref: Ref
    event_types: frozenset[str]
    scope_kinds: frozenset[str]
    on_match: str
    on_timeout: str
    probe: Callable[[AsyncConnection, Execution, Condition], Awaitable[Match | None]]
    handle: Callable[[AsyncConnection, Execution, Wait], Awaitable[Ref]]


class Policies:
    def __init__(self, items: Sequence[Policy]) -> None:
        self.items = tuple(items)
        if len({p.ref.model_dump_json() for p in items}) != len(items):
            raise ValueError("Duplicate wait policy")
        for item in items:
            if not item.event_types or not item.scope_kinds or not item.ref.revision:
                raise ValueError("Wait policy needs fixed revision, types and scopes")
            if any(
                not name.startswith(item.ref.owner + ".")
                for name in (item.on_match, item.on_timeout)
            ):
                raise ValueError("Wait handlers must belong to their owner")

    def resolve(self, wait: Wait, execution: Execution) -> Policy:
        policy = next((p for p in self.items if p.ref == wait.probe_ref), None)
        if (
            policy is None
            or policy.ref.owner != execution.owner
            or wait.owner_ref.owner != execution.owner
            or wait.execution_id != execution.execution_id
            or wait.on_match != policy.on_match
            or wait.on_timeout != policy.on_timeout
            or not set(wait.condition.event_types) <= policy.event_types
            or wait.condition.scope_kind not in policy.scope_kinds
            or wait.condition.scope_id != execution.scope_id
            or wait.condition.scope_kind != execution.scope_kind
        ):
            raise PermissionError("Wait policy or resource scope is not authorized")
        return policy
