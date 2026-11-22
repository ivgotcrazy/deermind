"""教材侧提交及原收据查询。"""

from typing import Literal, Protocol
from uuid import UUID

from deermind.abstractions.events import FactModel, Ref
from deermind.abstractions.material_intake import CandidateRef, ParentBinding
from deermind.foundation.system.public.errors import Issue
from deermind.product.public.authentication import SessionView
from deermind.product.public.materials import RequestId
from pydantic import Field

SUBMIT_INTAKE = "product.submit_domain_intake"


class SubmitDomainIntake(FactModel):
    request_id: RequestId
    adopted_content_refs: list[CandidateRef] = Field(min_length=1, max_length=50)
    parent_bindings: list[ParentBinding] = Field(default=[], max_length=50)


class IntakeSubmissionView(FactModel):
    submission_id: UUID
    trigger_event_ref: UUID
    status: Literal["submitted", "received", "rejected"]
    domain_receipt_ref: Ref | None
    items: list[Ref]
    issues: list[Issue]
    wait_state: Literal["waiting", "timed_out", "closed"]
    delivery_state: Literal["pending", "delivered", "exhausted", "unknown"]


class IntakeAccepted(FactModel):
    request_ref: UUID
    result: IntakeSubmissionView


class MaterialIntakeService(Protocol):
    async def submit(
        self, session: SessionView, import_id: UUID, command: SubmitDomainIntake
    ) -> IntakeAccepted: ...

    async def detail(
        self, session: SessionView, import_id: UUID, submission_id: UUID
    ) -> IntakeSubmissionView: ...
