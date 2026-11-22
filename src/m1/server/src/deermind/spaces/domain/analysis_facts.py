"""定义提取和实例归类的固定输入及结果事件。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    Ref,
    StoredEvent,
)

INPUT = "DomainAnalysisInputFixed"
TEMPLATE = "DomainTemplateCandidatePrepared"
CLASSIFIED = "DomainClassificationPrepared"
_TRIAL_CLASSIFIED = "DomainInstanceClassificationChecked"
ARTIFACT = "domain.artifact"


class AnalysisArtifact(FactModel):
    artifact_id: UUID
    domain_id: UUID
    kind: Literal["input", "definition_candidate", "classification_check"]
    input_ref: Ref
    definition_refs: list[Ref]
    payload: dict[str, JsonValue]
    rule_ref: Ref | None
    model_call_ref: Ref | None
    command_ref: Ref | None
    created_at: datetime


class AnalysisFact(EventPayload):
    domain_id: UUID
    request_ref: UUID
    artifact_ref: Ref
    intake_item_ref: Ref


def validate(draft: EventDraft, payload: EventPayload) -> None:
    if (
        not isinstance(payload, AnalysisFact)
        or payload.domain_id != draft.scope_id
        or len(payload.records) != 1
        or payload.records[0].record_type != ARTIFACT
        or payload.records[0].record_id != payload.artifact_ref.id
    ):
        raise ValueError("Analysis artifact does not match the event")


REGISTRATIONS = [
    EventRegistration(
        kind,
        1,
        "domain",
        "domain",
        AnalysisFact,
        validate,
        {
            (ARTIFACT, 1): AnalysisArtifact,
        },
    )
    for kind in (INPUT, TEMPLATE, CLASSIFIED, _TRIAL_CLASSIFIED)
]


async def project(connection: AsyncConnection, event: StoredEvent, value: AnalysisArtifact) -> None:
    await connection.execute(
        text(
            "INSERT INTO domain.artifact SELECT * FROM "
            "jsonb_populate_record(NULL::domain.artifact,CAST(:content AS jsonb))"
        ),
        {
            "content": canonical_json(
                {
                    **value.model_dump(mode="json"),
                    "source_event_id": str(event.draft.event_id),
                }
            )
        },
    )
