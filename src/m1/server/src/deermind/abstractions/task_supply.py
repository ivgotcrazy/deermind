"""Interaction 和 Domain 共享的供题请求及结果事实。"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from deermind.abstractions.events import EventPayload, FactModel, Ref

REQUESTED = "TaskSupplyRequested"
COMPLETED = "DomainTaskSupplyCompleted"
type SupplyPurpose = Literal["example", "practice", "assessment"]


class TaskSupplyRequested(EventPayload):
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
    trigger_event_id: UUID
    supply_batch_ref: Ref
    result_ref: Ref


class SuppliedTask(FactModel):
    task_instance_ref: Ref
    content_ref: Ref
    reference_solution_refs: list[Ref]
    matched_method_refs: list[Ref]
    use_check_ref: Ref
    source: Literal["existing", "generated"]


class UnfilledSupply(FactModel):
    count: Annotated[int, Field(gt=0)]
    condition: str | None
    reason: Literal["exposure_unknown", "requires_semantic_check", "no_eligible_instance"]
    retryable: bool
