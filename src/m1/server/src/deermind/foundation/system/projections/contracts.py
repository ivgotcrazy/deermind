"""通用维护记录和结果事件；副本元数据由所属业务解释。

分层定位：foundation（公共运行底座 / 投影重建契约）
对外契约：ScopeBound/RebuildJob/CheckIssue/RebuildFinished 定义重建作业与结果事件的数据合同。
边界约束：本模块只维护 runtime 层通用记录，不解释各业务副本的元数据。
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    NonEmpty,
    Ref,
)
from pydantic import Field, JsonValue


class ScopeBound(FactModel):
    """单个范围的重建上界：范围类型、编号与已封上界序号。"""

    scope_kind: NonEmpty
    scope_id: UUID
    upper_seq: Annotated[int, Field(ge=0)]


class RebuildJob(FactModel):
    """一次投影重建作业的登记记录：目标投影器、生成号、实现摘要、范围上界与状态。"""

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
    """重建过程中发现的一条核对问题：错误码、路径、说明与关联引用。"""

    code: NonEmpty
    path: str
    message: NonEmpty
    related_ref: Ref | None = None


class RebuildFinished(EventPayload):
    """重建结束结果事件正文：结果、投影器、生成号、范围上界与核对问题。"""

    subject_ref: Ref
    outcome: Literal["completed", "failed"]
    reason_code: NonEmpty | None
    projector_id: NonEmpty
    generation: Annotated[int, Field(gt=1)]
    scope_bounds: list[ScopeBound]
    checks: list[CheckIssue]


def validate_finished(draft: EventDraft, payload: EventPayload) -> None:
    """校验结果事件的主体、范围、失败原因与记录集合一致。"""
    # 类型不符、夹带记录、无范围上界、主体/归属不一致，或失败与原因码不配对，均判无效。
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


# ProjectionRebuildFinished 事件的类型、版本、生产者与正文 Schema 登记。
REBUILD_FINISHED = EventRegistration(
    event_type="ProjectionRebuildFinished",
    schema_version=1,
    producer="runtime",
    scope_kind="maintenance",
    payload_model=RebuildFinished,
    validate=validate_finished,
)
