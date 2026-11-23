"""Fixed course checks, applications and learning-space views."""

from datetime import datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID

from deermind.abstractions.events import FactModel, Ref
from deermind.foundation.system.files.uploads import JsonUUID
from deermind.foundation.system.public.errors import Issue
from deermind.product.public.authentication import AccountView
from deermind.product.public.chapter_associations import ChapterAssociationView
from deermind.product.public.learning_targets import GoalItem, TargetRef
from deermind.product.public.materials import RequestId, Revision
from deermind.spaces.evaluation.public import GoalEvaluation
from pydantic import Field, JsonValue

CHECK_COURSE = "product.check_course"
CONFIRM_COURSE = "product.confirm_course"
OPEN_SPACE = "product.open_learning_space"


class ChapterSelection(FactModel):
    chapter_id: JsonUUID
    revision: Revision
    content_refs: list[Ref]


class CourseCheckCommand(FactModel):
    request_id: RequestId
    textbook_id: JsonUUID
    target_ref: TargetRef
    expected_application_ref: Ref | None
    chapters: list[ChapterSelection] = Field(min_length=1)
    activity_config_refs: list[Ref]


class CourseConfirmCommand(FactModel):
    request_id: RequestId
    check_ref: Ref
    expected_application_ref: Ref | None


class ChapterSnapshot(FactModel):
    chapter_id: UUID
    revision: int
    title: str
    page_refs: list[Ref]
    content_refs: list[Ref]
    associations: list[ChapterAssociationView]


type Purpose = Literal[
    "reading", "explanation", "qa", "practice_feedback", "detection", "evaluation"
]


class PurposeCheck(FactModel):
    subject_ref: Ref
    purpose: Purpose
    status: Literal["ready", "limited", "blocked"]
    reasons: list[Issue]
    basis_refs: list[Ref]


class EvaluationGap(FactModel):
    item_id: UUID
    method_id: UUID
    method_version: int
    aspect_code: str
    reasons: list[str]


class CourseSnapshot(FactModel):
    textbook_title: str
    target_ref: TargetRef
    target_title: str
    chapters: list[ChapterSnapshot]
    activity_config_refs: list[Ref]
    readiness: list[PurposeCheck]
    items: list[GoalItem]
    evaluation_gaps: list[EvaluationGap]


class CourseCheckResult(FactModel):
    check_ref: Ref
    base_application_ref: Ref | None
    proposed_application: CourseSnapshot
    changes: list[Issue]
    readiness: list[PurposeCheck]
    can_apply: bool


class CourseCheckReceipt(FactModel):
    request_ref: UUID
    result: CourseCheckResult


class CourseApplyResult(FactModel):
    application_ref: Ref
    changed: bool
    affected_spaces: list[UUID]


class CourseApplyReceipt(FactModel):
    request_ref: UUID
    result: CourseApplyResult


class CourseOption(FactModel):
    textbook_id: UUID
    textbook_title: str
    target_ref: TargetRef
    target_title: str
    application_ref: Ref


class CourseOptions(FactModel):
    items: list[CourseOption]
    next_cursor: str | None


class CreateSpace(FactModel):
    request_id: RequestId
    action: Literal["create"]
    textbook_id: JsonUUID
    target_id: JsonUUID
    expected_application_ref: Ref


class EnterSpace(FactModel):
    request_id: RequestId
    action: Literal["enter"]
    space_id: JsonUUID


type SpaceCommand = Annotated[CreateSpace | EnterSpace, Field(discriminator="action")]


class SpaceRow(FactModel):
    space_id: UUID
    student_id: UUID
    student_name: str
    textbook_id: UUID
    textbook_title: str
    target_id: UUID
    target_title: str
    created_at: datetime


class SpaceList(FactModel):
    items: list[SpaceRow]
    next_cursor: str | None


class AdoptionView(FactModel):
    adoption_ref: Ref
    application_ref: Ref
    target_basis_ref: Ref
    snapshot: CourseSnapshot


class SpaceWorkspace(FactModel):
    space: SpaceRow
    adoption: AdoptionView


class SpaceOpenResult(SpaceWorkspace):
    created: bool
    entry_event_ref: UUID


class SpaceReceipt(FactModel):
    request_ref: UUID
    result: SpaceOpenResult


class ApplicationHead(FactModel):
    application_ref: Ref | None


class SpaceGoalView(FactModel):
    target_basis_ref: Ref
    target_title: str
    domain_id: UUID
    pending: bool
    current: GoalEvaluation | None
    evaluation_processing: Literal["pending", "failed"] | None = None


class SpaceChapterContent(FactModel):
    items: list[dict[str, JsonValue]]


class CourseCheckService(Protocol):
    async def head(self, textbook: UUID, target: UUID) -> ApplicationHead: ...
    async def check(self, principal: UUID, command: CourseCheckCommand) -> CourseCheckReceipt: ...


class CourseApplyService(Protocol):
    async def confirm(
        self, principal: UUID, command: CourseConfirmCommand
    ) -> CourseApplyReceipt: ...


class LearningSpaceService(Protocol):
    async def open(self, account: AccountView, command: SpaceCommand) -> SpaceReceipt: ...
    async def options(
        self,
        account: AccountView,
        domain: UUID | None,
        cursor: str | None,
        limit: int,
    ) -> CourseOptions: ...
    async def list_spaces(
        self,
        account: AccountView,
        student: UUID | None,
        textbook: UUID | None,
        target: UUID | None,
        name: str,
        cursor: str | None,
        limit: int,
    ) -> SpaceList: ...
    async def current_adoption(self, account: AccountView, space_id: UUID) -> AdoptionView: ...
    async def workspace(self, account: AccountView, space_id: UUID) -> SpaceWorkspace: ...
    async def current_goal(self, account: AccountView, space_id: UUID) -> SpaceGoalView: ...
    async def chapter_content(
        self,
        account: AccountView,
        scope: UUID,
        chapter: UUID,
    ) -> list[dict[str, JsonValue]]: ...
    async def list_events(
        self,
        scope: UUID,
        event_types: tuple[str, ...],
        after: int,
        upper: int | None,
        limit: int,
    ) -> dict[str, JsonValue]: ...
