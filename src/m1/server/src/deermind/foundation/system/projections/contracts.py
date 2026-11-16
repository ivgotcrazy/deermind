"""重建只登记确定性行转换；执行身份和副本位置不能由业务输入指定。"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from deermind.foundation.system.events.contracts import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    NonEmpty,
    Ref,
    StoredEvent,
)
from pydantic import Field, JsonValue
from sqlalchemy.ext.asyncio import AsyncConnection


class ScopeBound(FactModel):
    scope_kind: NonEmpty
    scope_id: UUID
    upper_seq: Annotated[int, Field(ge=0)]


class RebuildJob(FactModel):
    rebuild_id: UUID
    projector_id: NonEmpty
    generation: Annotated[int, Field(gt=1)]
    implementation_digest: str
    scope_bounds: list[ScopeBound]
    stage_relation: NonEmpty
    operator_id: NonEmpty
    authorization_ref: NonEmpty
    state: Literal["building", "completed", "failed"]
    result_event_id: UUID | None
    error: dict[str, JsonValue] | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RebuildSpec:
    """程序白名单：本轮业务事实生成一行，审计事实只推进扫描，不接受任意表、SQL或回调。"""

    projector_id: str
    scope_kind: str
    target: str
    key: str
    columns: tuple[str, ...]
    implementation_digest: str
    values: Callable[[StoredEvent], dict[str, object] | None]


class CheckIssue(FactModel):
    code: NonEmpty
    path: str
    message: NonEmpty
    related_ref: Ref | None = None


class RebuildFinished(EventPayload):
    subject_ref: Ref
    outcome: Literal["completed", "failed"]
    reason_code: NonEmpty | None
    projector_id: NonEmpty
    generation: Annotated[int, Field(gt=1)]
    scope_bounds: list[ScopeBound]
    checks: list[CheckIssue]


def validate_finished(draft: EventDraft, payload: EventPayload) -> None:
    if (
        not isinstance(payload, RebuildFinished)
        or payload.records
        or not payload.scope_bounds
        or payload.subject_ref != draft.owner_ref
        or draft.owner_ref
        != Ref(owner="runtime", type="projection_rebuild", id=str(draft.scope_id))
        or (payload.outcome == "failed") != (payload.reason_code is not None)
    ):
        raise ValueError("Invalid projection maintenance result")


async def no_business_projection(connection: AsyncConnection, event: StoredEvent) -> None:
    """维护结果只有事实，不创建业务查询行、通知或执行工作。"""


REBUILD_FINISHED = EventRegistration(
    event_type="ProjectionRebuildFinished",
    schema_version=1,
    producer="runtime",
    scope_kind="maintenance",
    payload_model=RebuildFinished,
    validate=validate_finished,
    projector_id="runtime.maintenance.v1",
    project=no_business_projection,
)
