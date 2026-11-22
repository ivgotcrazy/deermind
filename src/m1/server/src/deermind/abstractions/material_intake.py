"""教材提交给 Domain 的固定来源与父题选择合同。"""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import EventPayload, FactModel, Ref

type JsonUUID = Annotated[UUID, Field(strict=False)]
type CandidateKey = tuple[UUID, int, int]

REQUESTED = "DomainIntakeRequested"
RECEIVED = "DomainIntakeReceived"
REJECTED = "DomainIntakeRejected"
DELETED = "MaterialImportDeleted"


class CandidateRef(FactModel):
    candidate_id: JsonUUID
    candidate_revision: Annotated[int, Field(ge=1)]
    basis_revision: Annotated[int, Field(ge=0)]

    def key(self) -> CandidateKey:
        return self.candidate_id, self.candidate_revision, self.basis_revision


class ParentBinding(FactModel):
    candidate_ref: CandidateRef
    parent_candidate_ref: CandidateRef | None = None
    parent_item_ref: Ref | None = None
    task_instance_ref: Ref | None = None

    @model_validator(mode="after")
    def one_parent(self) -> Self:
        selected = (self.parent_candidate_ref, self.parent_item_ref, self.task_instance_ref)
        if sum(reference is not None for reference in selected) != 1:
            raise ValueError("A reference needs exactly one parent")
        for ref, kind, version in (
            (self.parent_item_ref, "intake_item", "revision"),
            (self.task_instance_ref, "task_instance", "version"),
        ):
            if ref is not None:
                UUID(ref.id)
                if ref.owner != "domain" or ref.type != kind or getattr(ref, version) is None:
                    raise ValueError("A stored parent must be a fixed Domain reference")
        return self


class IntakeSource(FactModel):
    candidate_ref: CandidateRef
    candidate_fact: EventPartRef
    adoption_ref: Ref


class IntakeRequested(EventPayload):
    domain_id: UUID
    intake_request_id: UUID
    candidate_refs: list[CandidateRef]
    sources: list[IntakeSource]
    parent_bindings: list[ParentBinding]


class IntakeDecided(EventPayload):
    trigger_event_id: UUID
    domain_id: UUID
    intake_request_id: UUID
    receipt_ref: Ref
    result_ref: Ref
    outcome: Literal["received", "rejected"]
    items: list[Ref]
    issues: list[dict[str, str]]
