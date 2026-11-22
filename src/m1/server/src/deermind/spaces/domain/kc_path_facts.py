"""直接检验路径及不足记录的完整事实格式。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    FactRecord,
    InlineContent,
    Ref,
)
from deermind.foundation.system.public.errors import Issue
from deermind.spaces.domain.facts import version_ref
from deermind.spaces.domain.public import KnowledgeRef, SolutionRef, TaskRef

CONFIRMED = "DomainKCTestPathConfirmed"
NOT_READY = "DomainKCTestPathNotReady"
ARTIFACT_TYPE = "domain.artifact"
PATH_TYPE = "domain.kc_test_path"


class PathBasis(FactModel):
    outcome: Literal["confirmed", "not_ready"]
    responsibility_ref: Ref
    observable_behavior: str
    insufficient_examples: list[str]
    issues: list[Issue]


class PathArtifact(FactModel):
    artifact_id: UUID
    domain_id: UUID
    kind: Literal["readiness_check"] = "readiness_check"
    input_ref: None = None
    definition_refs: list[Ref]
    payload: PathBasis
    rule_ref: None = None
    model_call_ref: None = None
    command_ref: Ref
    created_at: datetime


class PathRecord(FactModel):
    confirmation_id: UUID
    kc_id: UUID
    kc_version: int
    task_id: UUID
    task_version: int
    solution_id: UUID
    solution_version: int
    basis_artifact_id: UUID
    confirmed_by: Ref
    confirmed_at: datetime


class KCPathEvent(EventPayload):
    confirmation_ref: Ref | None
    basis_ref: Ref
    kc_ref: KnowledgeRef
    task_ref: TaskRef
    solution_ref: SolutionRef
    request_ref: UUID


def path_ref(confirmation_id: UUID) -> Ref:
    return Ref(owner="domain", type="kc_test_path", id=str(confirmation_id))


def basis_ref(artifact_id: UUID) -> Ref:
    return Ref(owner="domain", type="artifact", id=str(artifact_id))


def path_records(payload: KCPathEvent) -> tuple[PathArtifact, PathRecord | None]:
    records: dict[str, FactRecord] = {}
    for record in payload.records:
        if not isinstance(record.content, InlineContent) or record.record_type in records:
            raise ValueError("A path event requires distinct, complete records")
        records[record.record_type] = record
    artifact_record = records.pop(ARTIFACT_TYPE, None)
    path_record = records.pop(PATH_TYPE, None)
    if artifact_record is None or records:
        raise ValueError("A path event has unexpected records")
    assert isinstance(artifact_record.content, InlineContent)
    artifact = PathArtifact.model_validate_json(canonical_json(artifact_record.content.value))
    if artifact_record.record_id != str(artifact.artifact_id):
        raise ValueError("A path basis must use its stable identity")
    if path_record is None:
        return artifact, None
    assert isinstance(path_record.content, InlineContent)
    confirmation = PathRecord.model_validate_json(canonical_json(path_record.content.value))
    if path_record.record_id != str(confirmation.confirmation_id):
        raise ValueError("A path record must use its stable identity")
    return artifact, confirmation


def validate_path_event(draft: EventDraft, payload: EventPayload) -> None:
    if not isinstance(payload, KCPathEvent):
        raise ValueError("Invalid path event payload")
    artifact, path = path_records(payload)
    refs = [version_ref(ref) for ref in (payload.kc_ref, payload.task_ref, payload.solution_ref)]
    if (
        artifact.domain_id != draft.scope_id
        or artifact.definition_refs != refs
        or artifact.payload.responsibility_ref
        != refs[1].model_copy(update={"path": "/responsibility"})
        or payload.basis_ref != basis_ref(artifact.artifact_id)
        or artifact.command_ref
        != Ref(owner="domain", type="command_receipt", id=str(payload.request_ref))
    ):
        raise ValueError("Path basis and its source versions do not match")
    if draft.event_type == NOT_READY:
        if (
            path is not None
            or payload.confirmation_ref is not None
            or draft.owner_ref != payload.basis_ref
            or artifact.payload.outcome != "not_ready"
            or not artifact.payload.issues
        ):
            raise ValueError("An incomplete check cannot confirm a path")
        return
    if (
        path is None
        or payload.confirmation_ref != path_ref(path.confirmation_id)
        or draft.owner_ref != payload.confirmation_ref
        or artifact.payload.outcome != "confirmed"
        or artifact.payload.issues
        or path.basis_artifact_id != artifact.artifact_id
        or path.confirmed_at != artifact.created_at
        or (path.kc_id, path.kc_version) != (payload.kc_ref.object_id, payload.kc_ref.version)
        or (path.task_id, path.task_version)
        != (payload.task_ref.object_id, payload.task_ref.version)
        or (path.solution_id, path.solution_version)
        != (payload.solution_ref.object_id, payload.solution_ref.version)
    ):
        raise ValueError("A confirmed path must match its checked versions and basis")


PATH_REGISTRATIONS = [
    EventRegistration(
        event_type=event,
        schema_version=1,
        producer="domain",
        scope_kind="domain",
        payload_model=KCPathEvent,
        validate=validate_path_event,
        record_models=models,
    )
    for event, models in (
        (CONFIRMED, {(ARTIFACT_TYPE, 1): PathArtifact, (PATH_TYPE, 1): PathRecord}),
        (NOT_READY, {(ARTIFACT_TYPE, 1): PathArtifact}),
    )
]
