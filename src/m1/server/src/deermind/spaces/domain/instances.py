"""领域题目实例的固定版本读取、引用保护及事实准备。"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, FactRecord, InlineContent, Ref
from deermind.foundation.system.public.errors import RequestError
from deermind.spaces.domain import instance_facts as facts
from deermind.spaces.domain.public import (
    InstanceRef,
    InstanceView,
    KnowledgeRef,
    SolutionRef,
    TaskDefinition,
    TaskInstance,
    TaskRef,
)


async def load_instance(
    connection: AsyncConnection,
    domain_id: UUID,
    identity: UUID,
    version: int | None = None,
) -> InstanceView:
    row = (
        await connection.execute(
            text(
                "SELECT v.version,v.content,v.is_deleted FROM domain.object_identity i "
                "JOIN domain.object_version v USING(object_id) "
                "WHERE i.domain_id=:domain AND i.object_id=:id AND i.kind='task_instance' "
                "AND v.version=COALESCE(CAST(:version AS bigint),i.head_version)"
            ),
            {"domain": domain_id, "id": identity, "version": version},
        )
    ).one_or_none()
    if row is None:
        # 实例不存在或指定版本已删除。
        raise RequestError(404, "not_found", "找不到此题目实例。")
    return InstanceView(
        instance_ref=InstanceRef(object_id=identity, version=row.version),
        content=TaskInstance.model_validate_json(canonical_json(row.content)),
        is_deleted=row.is_deleted,
    )


async def require_definition(
    connection: AsyncConnection,
    domain_id: UUID,
    reference: TaskRef | SolutionRef | KnowledgeRef,
) -> dict[str, object]:
    value = await connection.scalar(
        text(
            "SELECT v.content FROM domain.object_identity i "
            "JOIN domain.object_version v USING(object_id) "
            "JOIN domain.object_version h ON (h.object_id,h.version)=(i.object_id,i.head_version) "
            "WHERE i.domain_id=:domain AND i.object_id=:id AND i.kind=:kind "
            "AND v.version=:version AND NOT v.is_deleted AND NOT h.is_deleted"
        ),
        {
            "domain": domain_id,
            "id": reference.object_id,
            "kind": reference.kind,
            "version": reference.version,
        },
    )
    if value is None:
        # 定义或其头部版本已删除，不可采用。
        raise RequestError(409, "invalid_reference", "所选定义已不可采用。")
    return value


async def evaluation_task(
    connection: AsyncConnection,
    domain_id: UUID,
    reference: TaskRef,
) -> TaskDefinition:
    """锁定领域目录后核对评价可使用的 Task 和各直接方法版本。"""
    root = await connection.scalar(
        text(
            "SELECT object_id FROM domain.object_identity "
            "WHERE object_id=:id AND kind='domain' FOR UPDATE"
        ),
        {"id": domain_id},
    )
    if root is None:
        raise RequestError(404, "not_found", "找不到领域。")
    task = TaskDefinition.model_validate(await require_definition(connection, domain_id, reference))
    for method in task.method_refs:
        # 任务各直接方法也须处于可采用版本。
        await require_definition(connection, domain_id, method)
    return task


async def validate_instance(
    connection: AsyncConnection,
    domain_id: UUID,
    instance: TaskInstance,
) -> None:
    if instance.statement.role != "statement" or not instance.statement.blocks:
        # 题面须为 statement 且含正文块。
        raise RequestError(400, "invalid_request", "题面正文必填。")
    definition = await require_definition(connection, domain_id, instance.task_ref)
    task = TaskDefinition.model_validate_json(canonical_json(definition))
    ids = {solution.reference_id for solution in instance.reference_solutions}
    if len(ids) != len(instance.reference_solutions):
        raise RequestError(400, "invalid_reference", "题内参考编号不能重复。")
    for solution in instance.reference_solutions:
        if solution.solution_ref not in task.method_refs:
            raise RequestError(409, "confirmation_required", "所选方法尚未加入此任务版本。")
        if solution.content.role != "reference" or not solution.content.blocks:
            raise RequestError(400, "invalid_request", "题内参考需要独立正文。")
        await require_definition(connection, domain_id, solution.solution_ref)


async def chapter_methods(
    connection: AsyncConnection,
    domain_id: UUID,
    task_ref: TaskRef,
    methods: list[SolutionRef],
) -> list[KnowledgeRef]:
    """同库短事务内锁定领域，再验证固定任务与本章实际采用的直接方法。"""
    found = await connection.scalar(
        text(
            "SELECT object_id FROM domain.object_identity WHERE object_id=:id "
            "AND kind='domain' FOR UPDATE"
        ),
        {"id": domain_id},
    )
    if found is None:
        raise RequestError(404, "not_found", "找不到领域。")
    task = TaskDefinition.model_validate(await require_definition(connection, domain_id, task_ref))
    seen: set[tuple[UUID, int]] = set()
    knowledge: list[KnowledgeRef] = []
    for method in methods:
        if method not in task.method_refs:
            raise RequestError(409, "invalid_reference", "所选方法不属于本任务版本。")
        from deermind.spaces.domain.public import SolutionDefinition

        solution = SolutionDefinition.model_validate(
            await require_definition(connection, domain_id, method)
        )
        derived = list(solution.kc_refs)
        if task.knowledge_ref:
            derived.append(task.knowledge_ref)
        for dependency in solution.dependencies or []:
            target = TaskDefinition.model_validate(
                await require_definition(connection, domain_id, dependency.task_ref)
            )
            if target.knowledge_ref:
                derived.append(target.knowledge_ref)
        for item in derived:
            key = (item.object_id, item.version)
            if key not in seen:
                # 同一知识成分去重，首次出现时核对可采用性。
                await require_definition(connection, domain_id, item)
                seen.add(key)
                knowledge.append(item)
    return knowledge


def instance_event(
    domain_id: UUID,
    identity: UUID,
    previous: InstanceRef | None,
    content: TaskInstance,
    actor: Ref,
    request: UUID,
    note: str,
    action: Literal["create", "update", "soft_delete"],
    checks: list[Ref],
) -> tuple[EventDraft, facts.InstanceVersion]:
    version = previous.version + 1 if previous else 1
    reference = InstanceRef(object_id=identity, version=version)
    value = facts.InstanceVersion(
        object_id=identity,
        version=version,
        content=content,
        is_deleted=action == "soft_delete",
        created_at=datetime.now(UTC),
        created_by=actor,
        change_note=note,
    )
    payload = facts.InstanceSaved(
        records=[
            FactRecord(
                record_id=str(identity),
                record_type=facts.VERSION,
                schema_version=1,
                content=InlineContent(storage="inline", value=value.model_dump(mode="json")),
            )
        ],
        instance_ref=reference,
        previous_ref=previous,
        classification_check_refs=checks,
        action=action,
        request_ref=request,
    )
    return EventDraft(
        uuid4(),
        facts.SAVED,
        1,
        "domain",
        domain_id,
        reference.reference(),
        payload.model_dump(mode="json"),
        str(request),
    ), value
