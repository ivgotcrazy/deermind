"""Interaction 和 Domain 共享的供题请求及结果事实。

分层定位：abstractions（跨层合同）
对外契约：供题请求/完成事件正文，及已供题目、未满足项结构。
边界约束：只定义事件正文与结构，不含选题、生成与核验实现。
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from deermind.abstractions.events import EventPayload, FactModel, Ref

REQUESTED = "TaskSupplyRequested"
COMPLETED = "DomainTaskSupplyCompleted"
type SupplyPurpose = Literal["example", "practice", "assessment"]


class TaskSupplyRequested(EventPayload):
    """供题请求正文：用途、题目/方法/约束、已接触实例与所需数量。"""

    request_ref: Ref
    supply_input_ref: Ref
    domain_id: UUID
    activity_ref: Ref
    purpose: SupplyPurpose
    task_ref: Ref
    allowed_method_refs: list[Ref]
    assessment_constraints_ref: Ref
    assessment_constraints: str | None
    method_source_refs: list[Ref]
    exposure_refs: list[Ref]
    exposed_instances: list[Ref] | None
    count: Annotated[int, Field(gt=0)]


class DomainTaskSupplyCompleted(EventPayload):
    """供题完成正文：触发事件、供题批次引用与结果引用。"""

    trigger_event_id: UUID
    supply_batch_ref: Ref
    result_ref: Ref


class SuppliedTask(FactModel):
    """一道已供题目：实例、正文、参考解法、匹配方法、使用核验；来源为既有或生成。"""

    task_instance_ref: Ref
    content_ref: Ref
    reference_solution_refs: list[Ref]
    matched_method_refs: list[Ref]
    use_check_ref: Ref
    source: Literal["existing", "generated"]


class UnfilledSupply(FactModel):
    """未满足供题项：数量、条件、原因类别与是否可重试。"""

    count: Annotated[int, Field(gt=0)]
    condition: str | None
    reason: Literal["exposure_unknown", "requires_semantic_check", "no_eligible_instance"]
    retryable: bool
