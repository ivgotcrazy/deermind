"""教材范围内的学习目标及固定要求。"""

from typing import Annotated, Literal, Protocol
from uuid import UUID

from deermind.abstractions.events import FactModel, Ref
from deermind.foundation.system.files.uploads import JsonUUID
from deermind.foundation.system.public.errors import Issue
from deermind.product.public.materials import RequestId, Revision
from deermind.spaces.domain.public import SolutionRef
from deermind.spaces.evaluation.public import AspectCode, ClaimRef
from pydantic import Field, JsonValue, StringConstraints

SAVE_TARGET = "product.save_learning_target"
type Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]


class TargetRef(FactModel):
    target_id: JsonUUID
    revision: Revision


class TargetAspectRef(FactModel):
    claim_ref: ClaimRef
    aspect_code: AspectCode


class TargetAspect(FactModel):
    aspect_ref: TargetAspectRef
    condition_values: dict[str, JsonValue]


class MethodRequirement(FactModel):
    method_ref: SolutionRef
    chapter_refs: list[JsonUUID] = Field(min_length=1)
    aspects: list[TargetAspect] = Field(min_length=1)


class TaskConditions(FactModel):
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4096)]


class GoalItemFields(FactModel):
    title: Label
    claim_ref: ClaimRef
    chapter_refs: list[JsonUUID] = Field(min_length=1)
    task_conditions: TaskConditions
    method_mode: Literal["specified", "any_one", "each"]
    methods: list[MethodRequirement] = Field(min_length=1)


class GoalItemDraft(GoalItemFields):
    item_id: JsonUUID | None = None


class GoalItem(GoalItemFields):
    item_id: JsonUUID


class CreateTarget(FactModel):
    extraction_id: JsonUUID
    assessment_id: JsonUUID
    action: Literal["create"]
    request_id: RequestId
    textbook_id: JsonUUID
    title: Label
    items: list[GoalItemDraft] = Field(min_length=1)


class ReviseTarget(FactModel):
    extraction_id: JsonUUID
    assessment_id: JsonUUID
    action: Literal["update"]
    request_id: RequestId
    textbook_id: JsonUUID
    target_id: JsonUUID
    expected_revision: Revision
    title: Label
    items: list[GoalItemDraft] = Field(min_length=1)


type TargetCommand = Annotated[CreateTarget | ReviseTarget, Field(discriminator="action")]


class TargetView(FactModel):
    extraction_id: JsonUUID | None = None
    assessment_id: JsonUUID | None = None
    target_ref: TargetRef
    textbook_id: JsonUUID
    title: Label
    items: list[GoalItem]
    chapter_basis_refs: list[Ref]
    gaps: list[Issue]


class TargetDetail(FactModel):
    target: TargetView


class TargetList(FactModel):
    items: list[TargetView]
    next_cursor: str | None


class TargetReceipt(FactModel):
    request_ref: UUID
    result: TargetDetail


class LearningTargets(Protocol):
    async def list_targets(
        self,
        principal: UUID,
        textbook_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> TargetList: ...

    async def detail(self, target_id: UUID, revision: int | None) -> TargetDetail: ...

    async def save(self, principal: UUID, body: TargetCommand) -> TargetReceipt: ...
