"""只追加题目版本和题内参考，待办结果通过各自事件登记。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

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
from deermind.foundation.system.projections.receipts import application
from deermind.spaces.domain.intake import ITEM, IntakeItem
from deermind.spaces.domain.public import (
    InstanceRef,
    IntakeActionResult,
    SolutionRef,
    TaskInstance,
    TaskRef,
)

SAVED = "DomainInstanceSaved"
PROCESSED = "DomainIntakeItemProcessed"
INVALIDATED = "DomainIntakeSourceInvalidated"
VERSION = "domain.object_version"


class InstanceVersion(FactModel):
    object_id: UUID
    version: int
    content_schema_version: Literal[1] = 1
    content: TaskInstance
    is_deleted: bool
    created_at: datetime
    created_by: Ref
    change_note: str


class InstanceSaved(EventPayload):
    instance_ref: InstanceRef
    previous_ref: InstanceRef | None
    classification_check_refs: list[Ref]
    action: Literal["create", "update", "soft_delete"]
    request_ref: UUID


class ItemProcessed(EventPayload):
    domain_id: UUID
    request_ref: UUID
    result: IntakeActionResult


class SourceInvalidated(EventPayload):
    item_ref: Ref
    import_id: UUID
    trigger_event_id: UUID


def _validate(draft: EventDraft, payload: EventPayload) -> None:
    if isinstance(payload, InstanceSaved):
        if len(payload.records) != 1 or payload.records[0].record_type != VERSION:
            # 实例保存事件只含一条完整版本记录。
            raise ValueError("Instance save requires one full version")
        content = payload.records[0].content
        if not isinstance(content, InlineContent):
            raise ValueError("Expected a complete instance version")
        version = InstanceVersion.model_validate_json(canonical_json(content.value))
        ref = payload.instance_ref
        if (
            version.object_id != ref.object_id
            or version.version != ref.version
            or draft.owner_ref != ref.reference()
            or version.is_deleted != (payload.action == "soft_delete")
        ):
            raise ValueError("Instance version conflicts with the event")
        old = payload.previous_ref
        if old is None:
            # 新建实例无前版本，须从 v1 且动作 create。
            if ref.version != 1 or payload.action != "create":
                raise ValueError("New instances begin at version one")
        elif old.object_id != ref.object_id or old.version + 1 != ref.version:
            # 修订版本必须接在前一版本之后。
            raise ValueError("Instance history must be continuous")
    elif isinstance(payload, ItemProcessed):
        if payload.domain_id != draft.scope_id or not payload.records:
            raise ValueError("Missing intake result records")
        if any(record.record_type != ITEM for record in payload.records):
            # 处理结果只能回写关联的待办条目。
            raise ValueError("Intake result may only update related intake items")
    elif isinstance(payload, SourceInvalidated):
        if (
            payload.trigger_event_id != draft.causation_event_id
            or len(payload.records) != 1
            or payload.records[0].record_type != ITEM
            or payload.records[0].record_id != payload.item_ref.id
        ):
            raise ValueError("Source invalidation does not match its intake item")
    else:
        raise ValueError("Unknown instance event")


REGISTRATIONS = [
    EventRegistration(
        SAVED, 1, "domain", "domain", InstanceSaved, _validate, {(VERSION, 1): InstanceVersion}
    ),
    EventRegistration(
        PROCESSED, 1, "domain", "domain", ItemProcessed, _validate, {(ITEM, 1): IntakeItem}
    ),
    EventRegistration(
        INVALIDATED, 1, "domain", "domain", SourceInvalidated, _validate, {(ITEM, 1): IntakeItem}
    ),
]


async def project_instance(
    connection: AsyncConnection,
    event: StoredEvent,
    value: InstanceVersion,
) -> None:
    payload = event.payload
    assert isinstance(payload, InstanceSaved)
    domain = event.draft.scope_id
    async with application(connection, "domain.instances.v1", 1, event.draft.event_id) as apply:
        if not apply:
            # 回执不要求投影时跳过落库。
            return
        if payload.action == "create":
            # 新建先登记身份行，版本号置 1。
            await connection.execute(
                text(
                    "INSERT INTO domain.object_identity(object_id,kind,domain_id,head_version) "
                    "VALUES (:id,'task_instance',:domain,1)"
                ),
                {"id": value.object_id, "domain": domain},
            )
        await connection.execute(
            text(
                "INSERT INTO domain.object_version SELECT * FROM "
                "jsonb_populate_record(NULL::domain.object_version,CAST(:content AS jsonb))"
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
        if payload.action != "create":
            # 修订/软删后更新身份行的头部版本。
            await connection.execute(
                text("UPDATE domain.object_identity SET head_version=:version WHERE object_id=:id"),
                {"id": value.object_id, "version": value.version},
            )
        refs: list[tuple[str, str, TaskRef | SolutionRef]] = [
            ("instance_task", "/task_ref", value.content.task_ref)
        ]
        refs.extend(
            (
                "reference_solution",
                f"/reference_solutions/{index}/solution_ref",
                solution.solution_ref,
            )
            for index, solution in enumerate(value.content.reference_solutions)
        )  # 逐条登记题内参考解法引用
        await connection.execute(
            text(
                "INSERT INTO domain.object_reference "
                "(owner_id,owner_version,path,relation_kind,target_id,target_version) "
                "VALUES (:id,:version,:path,:kind,:target,:target_version)"
            ),
            [
                {
                    "id": value.object_id,
                    "version": value.version,
                    "path": path,
                    "kind": kind,
                    "target": reference.object_id,
                    "target_version": reference.version,
                }
                for kind, path, reference in refs
            ],
        )
        await connection.execute(
            text(
                "UPDATE domain.object_identity SET catalog_revision=catalog_revision+1 "
                "WHERE object_id=:id"
            ),
            {"id": domain},
        )


async def project_items(connection: AsyncConnection, event: StoredEvent) -> None:
    async with application(
        connection, "domain.intake_processing.v1", 1, event.draft.event_id
    ) as apply:
        if not apply:
            return
        for record in event.payload.records:
            # 逐条回写待办条目的修订、状态与结果引用。
            assert isinstance(record.content, InlineContent)
            item = IntakeItem.model_validate_json(canonical_json(record.content.value))
            await connection.execute(
                text(
                    "UPDATE domain.intake_item SET revision=:revision,state=:state,"
                    "result_ref=CAST(:result AS jsonb),processed_request_ref=:request,"
                    "source_event_id=:event WHERE item_id=:id AND revision=:previous"
                ),
                {
                    "id": item.item_id,
                    "revision": item.revision,
                    "previous": item.revision - 1,
                    "state": item.state,
                    "result": item.result_ref.model_dump_json() if item.result_ref else None,
                    "request": item.processed_request_ref,
                    "event": event.draft.event_id,
                },
            )
