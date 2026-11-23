"""Product owns the course and space projections and publishes fixed adoption facts."""

from datetime import datetime
from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    FactRecord,
    InlineContent,
    Ref,
    StoredEvent,
)
from deermind.foundation.system.projections.receipts import application
from deermind.foundation.system.public.errors import Issue
from deermind.product.public.courses import CourseCheckCommand, CourseSnapshot, PurposeCheck
from deermind.product.public.learning_targets import TargetRef
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

CHECKED = "ApplicationChecked"
APPLIED = "CourseApplied"
CREATED = "LearningSpaceCreated"
ADOPTION = "LearningSpaceAdoptionChanged"
TARGET_APPLIED = "LearningTargetApplied"
ENTERED = "LearningSpaceEntered"
CHECK = "product.application_check"
BASIS = "product.target_basis"
COURSE = "product.course_application"
SPACE = "product.learning_space"
SPACE_ADOPTION = "product.space_adoption"


class CheckRow(FactModel):
    check_id: UUID
    request_ref: UUID
    base_application_ref: Ref | None
    input: CourseCheckCommand
    proposed_application: CourseSnapshot
    purpose_checks: list[PurposeCheck]
    blockers: list[Issue]
    created_at: datetime


class BasisRow(FactModel):
    basis_id: UUID
    textbook_id: UUID
    target_id: UUID
    normalized_basis: dict[str, JsonValue]
    digest: str
    created_at: datetime


class CourseRow(FactModel):
    application_id: UUID
    textbook_id: UUID
    target_id: UUID
    previous_application_id: UUID | None
    check_ref: UUID
    content_snapshot: CourseSnapshot
    target_basis_ref: UUID
    actor_ref: Ref
    created_at: datetime


class SpaceHead(FactModel):
    space_id: UUID
    student_id: UUID
    textbook_id: UUID
    target_id: UUID
    current_adoption_ref: UUID
    created_at: datetime


class AdoptionRow(FactModel):
    adoption_id: UUID
    space_id: UUID
    adoption_seq: int
    application_ref: UUID
    target_basis_ref: UUID
    previous_adoption_id: UUID | None
    reason: str
    event_ref: UUID
    created_at: datetime


class ApplicationChecked(EventPayload):
    check_ref: Ref
    textbook_id: UUID
    target_ref: TargetRef
    check_status: str
    request_ref: UUID


class CourseApplied(EventPayload):
    application_ref: Ref
    previous_application_ref: Ref | None
    check_ref: Ref
    textbook_id: UUID
    target_ref: TargetRef
    request_ref: UUID


class LearningSpaceCreated(EventPayload):
    student_id: UUID
    textbook_id: UUID
    target_id: UUID
    adoption_ref: Ref


class LearningSpaceAdoptionChanged(EventPayload):
    previous_adoption_ref: Ref
    adoption_ref: Ref
    previous_target_basis_ref: Ref
    target_basis_ref: Ref
    cause_ref: Ref


class LearningTargetApplied(EventPayload):
    adoption_ref: Ref
    application_ref: Ref
    target_basis_ref: Ref
    previous_target_basis_ref: Ref | None
    applied_at: datetime
    cause_ref: Ref


class LearningSpaceEntered(EventPayload):
    adoption_ref: Ref
    application_ref: Ref
    target_basis_ref: Ref
    request_ref: UUID
    created: bool


SHAPES: dict[str, tuple[type[EventPayload], dict[str, type[FactModel]]]] = {
    CHECKED: (ApplicationChecked, {CHECK: CheckRow}),
    APPLIED: (CourseApplied, {BASIS: BasisRow, COURSE: CourseRow}),
    CREATED: (LearningSpaceCreated, {SPACE: SpaceHead, SPACE_ADOPTION: AdoptionRow}),
    ADOPTION: (LearningSpaceAdoptionChanged, {SPACE: SpaceHead, SPACE_ADOPTION: AdoptionRow}),
    TARGET_APPLIED: (LearningTargetApplied, {}),
    ENTERED: (LearningSpaceEntered, {}),
}


def validate(draft: EventDraft, payload: EventPayload) -> None:
    _, allowed = SHAPES[draft.event_type]
    kinds = {record.record_type for record in payload.records}
    required = allowed.keys() - ({BASIS} if draft.event_type == APPLIED else set())
    if not required <= kinds <= allowed.keys() or len(kinds) != len(payload.records):
        raise ValueError("Course fact records do not match its event type")
    for record in payload.records:
        assert isinstance(record.content, InlineContent)
        value = record.content.value
        if record.record_type in {SPACE, SPACE_ADOPTION} and value["space_id"] != str(
            draft.scope_id
        ):
            raise ValueError("Projection belongs to a different learning space")
        if record.record_type == SPACE_ADOPTION and value["event_ref"] != str(draft.event_id):
            raise ValueError("Adoption must cite its own fact")


REGISTRATIONS = [
    EventRegistration(
        kind,
        1,
        "product",
        "course_application" if kind in {CHECKED, APPLIED} else "learning_space",
        model,
        validate,
        {(table, 1): shape for table, shape in rows.items()},
    )
    for kind, (model, rows) in SHAPES.items()
]


def ref(kind: str, identity: UUID, revision: int | None = None) -> Ref:
    return Ref(owner="product", type=kind, id=str(identity), revision=revision)


def record(table: str, identity: UUID, row: FactModel) -> FactRecord:
    return FactRecord(
        record_id=str(identity),
        record_type=table,
        schema_version=1,
        content=InlineContent(storage="inline", value=row.model_dump(mode="json")),
    )


def event(
    kind: str,
    scope: tuple[str, UUID],
    owner: Ref,
    body: EventPayload,
    *,
    identity: UUID | None = None,
    request_id: str | None = None,
) -> EventDraft:
    return EventDraft(
        identity or uuid4(), kind, 1, *scope, owner, body.model_dump(mode="json"), request_id
    )


async def project(db: AsyncConnection, saved: StoredEvent) -> None:
    if not saved.payload.records:
        return
    async with application(db, "product.course_views", 1, saved.draft.event_id) as needed:
        if not needed:
            return
        # Event order puts the rows referenced by foreign keys first.
        for row in saved.payload.records:
            table = row.record_type
            assert isinstance(row.content, InlineContent)
            sql = (
                f"INSERT INTO {table} SELECT * FROM "
                f"jsonb_populate_record(NULL::{table},CAST(:body AS jsonb))"
            )
            if table == SPACE:
                sql += (
                    " ON CONFLICT(space_id) DO UPDATE "
                    "SET current_adoption_ref=EXCLUDED.current_adoption_ref,"
                    "source_event_id=EXCLUDED.source_event_id"
                )
            await db.execute(
                text(sql),
                {
                    "body": canonical_json(
                        {
                            **row.content.value,
                            "source_event_id": str(saved.draft.event_id),
                        }
                    )
                },
            )
            if table == COURSE:
                await db.execute(
                    text(
                        "INSERT INTO product.application_head "
                        "SELECT textbook_id,target_id,application_id,1 FROM "
                        "product.course_application "
                        "WHERE application_id=:id ON CONFLICT(textbook_id,target_id) DO UPDATE "
                        "SET current_application_ref=EXCLUDED.current_application_ref,"
                        "revision=product.application_head.revision+1"
                    ),
                    {"id": UUID(row.record_id)},
                )
