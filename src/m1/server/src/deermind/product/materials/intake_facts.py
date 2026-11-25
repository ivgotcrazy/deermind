"""教材的入库提交及受理结果投影。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    InlineContent,
    Ref,
    StoredEvent,
)
from deermind.abstractions.material_intake import (
    REQUESTED,
    CandidateRef,
    IntakeRequested,
    ParentBinding,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

STATUS = "MaterialIntakeStatusUpdated"
SUBMISSION = "product.material_intake_submission"


class SubmissionFact(FactModel):
    submission_id: UUID
    import_id: UUID
    candidate_refs: list[CandidateRef]
    parent_bindings: list[ParentBinding]
    trigger_event_id: UUID
    status: Literal["submitted", "received", "rejected"]
    domain_receipt_ref: Ref | None
    wait_state: Literal["waiting", "timed_out", "closed"]
    items: list[Ref]
    issues: list[dict[str, str]]
    created_at: datetime


class IntakeStatusUpdated(EventPayload):
    submission_id: UUID
    domain_event_id: UUID
    domain_receipt_ref: Ref
    outcome: Literal["received", "rejected"]


def validate(draft: EventDraft, payload: EventPayload) -> None:
    if not isinstance(payload, (IntakeRequested, IntakeStatusUpdated)) or len(payload.records) != 1:
        raise ValueError("Expected one material submission fact")
    row = payload.records[0]
    if row.record_type != SUBMISSION or not isinstance(row.content, InlineContent):
        raise ValueError("Expected complete material submission")
    content = SubmissionFact.model_validate_json(canonical_json(row.content.value))
    if content.import_id != draft.scope_id or str(content.submission_id) != row.record_id:
        # 提交作用域与记录身份须一致。
        raise ValueError("Submission scope does not match")
    if isinstance(payload, IntakeRequested) and (
        content.trigger_event_id != draft.event_id
        or payload.intake_request_id != content.submission_id
        or payload.candidate_refs != content.candidate_refs
        or payload.parent_bindings != content.parent_bindings
        or payload.candidate_refs != [source.candidate_ref for source in payload.sources]
    ):
        # 请求事件的触发、候选与父题绑定须与落库提交一致。
        raise ValueError("Submission sources do not match")


REGISTRATIONS = [
    EventRegistration(
        kind, 1, "product", "material_import", model, validate, {(SUBMISSION, 1): SubmissionFact}
    )
    for kind, model in ((REQUESTED, IntakeRequested), (STATUS, IntakeStatusUpdated))
]


async def project(connection: AsyncConnection, event: StoredEvent) -> None:
    row = event.payload.records[0]
    if not isinstance(row.content, InlineContent):
        raise ValueError("Submission projection requires complete fact")
    await connection.execute(
        text(
            "INSERT INTO product.material_intake_submission SELECT * FROM "
            "jsonb_populate_record(NULL::product.material_intake_submission,CAST(:value AS jsonb)) "
            "ON CONFLICT(submission_id) DO UPDATE SET status=excluded.status,"
            "domain_receipt_ref=excluded.domain_receipt_ref,wait_state=excluded.wait_state,"
            "items=excluded.items,issues=excluded.issues,"
            "source_event_id=excluded.source_event_id"
        ),
        {
            "value": canonical_json(
                {
                    **row.content.value,
                    "source_event_id": str(event.draft.event_id),
                }
            )
        },
    )
