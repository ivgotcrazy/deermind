"""通用维护记录和结果事件；副本元数据由所属业务解释。"""

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
)
from pydantic import Field, JsonValue


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
    target_relations: dict[str, str]
    operator_id: NonEmpty
    authorization_ref: NonEmpty
    state: Literal["building", "completed", "failed"]
    result_event_id: UUID | None
    error: dict[str, JsonValue] | None
    created_at: datetime
    updated_at: datetime


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


REBUILD_FINISHED = EventRegistration(
    event_type="ProjectionRebuildFinished",
    schema_version=1,
    producer="runtime",
    scope_kind="maintenance",
    payload_model=RebuildFinished,
    validate=validate_finished,
)
