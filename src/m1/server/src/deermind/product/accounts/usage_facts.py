"""监护和首次确认的完整事实正文；投影只保存已接受的决定，不重新计算同意。"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from deermind.foundation.system.events.contracts import FactModel, NonEmpty, Ref
from pydantic import Field

Revision = Annotated[int, Field(ge=1)]


class UsageIssue(FactModel):
    code: NonEmpty
    path: str
    message: NonEmpty


class GuardianFact(FactModel):
    guardian_id: UUID
    verified_identity_ref: Ref
    display_name: NonEmpty
    created_at: datetime


class RelationFact(FactModel):
    relation_id: UUID
    student_id: UUID
    guardian_id: UUID
    revision: Revision
    verification_ref: Ref
    relation_state: Literal["active", "ended"]
    previous_relation_id: UUID | None
    actor_ref: Ref
    created_at: datetime


class ConfirmationFact(FactModel):
    confirmation_id: UUID
    student_id: UUID
    kind: Literal["guardian_consent", "student_assent"]
    notice_ref: Ref
    decision: Literal["accepted", "declined", "pending"]
    source_ref: Ref
    actor_ref: Ref
    occurred_at: datetime | None
    created_at: datetime


class ConditionsFact(FactModel):
    student_id: UUID
    revision: Revision
    confirmation_refs: list[Ref]
    eligibility: Literal["allowed", "blocked", "pending"]
    reasons: list[UsageIssue]
    updated_at: datetime


USAGE_RECORDS: dict[tuple[str, int], type[FactModel]] = {
    ("product.guardian_records", 1): GuardianFact,
    ("product.student_guardian_relations", 1): RelationFact,
    ("product.usage_confirmations", 1): ConfirmationFact,
    ("product.usage_conditions", 1): ConditionsFact,
}
