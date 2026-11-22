"""领域定义保存的事件正文和固定版本记录。"""

from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import field_validator

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    InlineContent,
    Ref,
)
from deermind.spaces.domain.public import (
    DomainDefinition,
    DomainRef,
    KnowledgeComponent,
    NonBlank,
    ObjectRef,
    Version,
)

EVENT_TYPE = "DomainDefinitionSaved"
RECORD_TYPE = "domain.object_version"
RECORD_ID = "version"


class DomainVersion(FactModel):
    """事件中完整的 object_version v1 记录，生成投影时补来源事件。"""

    object_id: UUID
    version: Version
    content_schema_version: Literal[1]
    content: DomainDefinition | KnowledgeComponent
    is_deleted: bool
    created_at: datetime
    created_by: Ref
    change_note: NonBlank

    @field_validator("created_at")
    @classmethod
    def utc_time(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("Domain version timestamps must be UTC")
        return value


class DomainSaved(EventPayload):
    object_ref: ObjectRef
    previous_ref: ObjectRef | None
    action: Literal["create", "update", "soft_delete"]
    request_ref: UUID


def version_ref(object_ref: ObjectRef) -> Ref:
    return Ref(
        owner="domain",
        type=object_ref.kind,
        id=str(object_ref.object_id),
        version=object_ref.version,
    )


def version_content(payload: EventPayload) -> DomainVersion:
    """验证正文和版本投影使用同一固定记录。"""
    if not isinstance(payload, DomainSaved) or len(payload.records) != 1:
        raise ValueError("Domain save must contain one version record")
    record = payload.records[0]
    if (
        record.record_type != RECORD_TYPE
        or record.record_id != RECORD_ID
        or record.schema_version != 1
        or not isinstance(record.content, InlineContent)
    ):
        raise ValueError("Invalid domain version record")
    value = DomainVersion.model_validate_json(canonical_json(record.content.value))
    if (
        value.object_id != payload.object_ref.object_id
        or value.version != payload.object_ref.version
    ):
        raise ValueError("Domain object identity or version mismatch")
    return value


def validate_saved(draft: EventDraft, payload: EventPayload) -> None:
    if not isinstance(payload, DomainSaved):
        raise ValueError("Invalid domain save payload")
    value = version_content(payload)
    ref = payload.object_ref
    if draft.owner_ref != version_ref(ref):
        raise ValueError("Domain save does not match its scope or owner")
    if isinstance(ref, DomainRef):
        if (
            not isinstance(value.content, DomainDefinition)
            or draft.scope_id != ref.object_id
            or payload.action != "create"
        ):
            raise ValueError("Invalid Domain root definition")
    elif not isinstance(value.content, KnowledgeComponent) or draft.scope_id == ref.object_id:
        raise ValueError("Invalid knowledge component definition")

    previous = payload.previous_ref
    if payload.action == "create":
        if previous is not None or ref.version != 1:
            raise ValueError("A new definition must start at version one")
    elif (
        previous is None
        or previous.kind != ref.kind
        or previous.object_id != ref.object_id
        or previous.version != ref.version - 1
    ):
        raise ValueError("A revision must append to its previous version")
    if value.is_deleted != (payload.action == "soft_delete"):
        raise ValueError("The definition action and deletion state disagree")


DOMAIN_SAVED = EventRegistration(
    event_type=EVENT_TYPE,
    schema_version=1,
    producer="domain",
    scope_kind="domain",
    payload_model=DomainSaved,
    validate=validate_saved,
    record_models={(RECORD_TYPE, 1): DomainVersion},
)
