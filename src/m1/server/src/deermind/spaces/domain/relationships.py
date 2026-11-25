"""校验领域定义中的固定关系，并从同一事实生成查询索引。"""

from collections.abc import Sequence
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from deermind.foundation.system.public.errors import Issue, RequestError
from deermind.spaces.domain.public import (
    DefinitionContent,
    KnowledgeRef,
    KnowledgeSources,
    KnowledgeUse,
    MemberRef,
    SolutionDefinition,
    SolutionRef,
    TaskDefinition,
)

_RELATION_INSERT = text(
    "INSERT INTO domain.object_reference "
    "(owner_id,owner_version,path,relation_kind,target_id,target_version) "
    "VALUES (:owner,:owner_version,:path,:relation_kind,:target,:target_version)"
)
_EXACT_REFS = (
    "SELECT * FROM unnest(CAST(:ids AS uuid[]),CAST(:versions AS bigint[])) "
    "AS selected(object_id,version)"
)


class Relationship(NamedTuple):
    path: str
    kind: str
    ref: MemberRef


def references(content: DefinitionContent) -> list[Relationship]:
    if isinstance(content, SolutionDefinition):
        # 方法→知识成分关系。
        return [
            Relationship(f"/kc_refs/{index}", "solution_kc", ref)
            for index, ref in enumerate(content.kc_refs)
        ]
    if not isinstance(content, TaskDefinition):
        # 其他定义类型无可提取关系。
        return []
    entries = [
        Relationship(f"/method_refs/{index}", "task_method", ref)
        for index, ref in enumerate(content.method_refs)
    ]
    for index, link in enumerate(content.prerequisites):
        path = f"/prerequisites/{index}"
        entries.append(Relationship(f"{path}/task_ref", "task_prerequisite", link.task_ref))
        entries.extend(
            Relationship(f"{path}/method_refs/{position}", "prerequisite_method_scope", ref)
            for position, ref in enumerate(link.method_refs)
        )
    return entries


def relationship_error(path: str, message: str, code: str = "invalid_reference") -> RequestError:
    return RequestError(400, code, message, issues=[Issue(code=code, path=path, message=message)])


def _keys(refs: Sequence[MemberRef]) -> dict[str, list[UUID] | list[int]]:
    return {
        "ids": [ref.object_id for ref in refs],
        "versions": [ref.version for ref in refs],
    }


def _check_task_shape(content: TaskDefinition) -> None:
    methods = {(ref.object_id, ref.version) for ref in content.method_refs}
    for index, link in enumerate(content.prerequisites):
        path = f"/prerequisites/{index}/method_refs"
        if (link.applies_to == "specified") != bool(link.method_refs):
            # 指定适用范围必须带方法，反之不得带方法。
            raise relationship_error(path, "请按先导适用范围设置方法。")
        targets = [(ref.object_id, ref.version) for ref in link.method_refs]
        if len(set(targets)) != len(targets) or any(ref not in methods for ref in targets):
            raise relationship_error(path, "指定方法须为本任务直接采用的同一版本，且不可重复。")


async def validate_relationships(
    connection: AsyncConnection, domain_id: UUID, owner_id: UUID, content: DefinitionContent
) -> None:
    """在领域根锁内检查当前可采用性与精确先导图。"""
    if isinstance(content, TaskDefinition):
        _check_task_shape(content)
    entries = references(content)
    if not entries:
        # 无关系引用，无需核对。
        return
    rows = await connection.execute(
        text(
            f"WITH selected AS ({_EXACT_REFS}) "
            "SELECT i.object_id,v.version,i.kind FROM selected s "
            "JOIN domain.object_identity i ON i.object_id=s.object_id "
            "JOIN domain.object_version v ON (v.object_id,v.version)=(i.object_id,s.version) "
            "JOIN domain.object_version h ON (h.object_id,h.version)=(i.object_id,i.head_version) "
            "WHERE i.domain_id=:domain AND NOT v.is_deleted AND NOT h.is_deleted"
        ),
        {"domain": domain_id, **_keys([entry.ref for entry in entries])},
    )
    allowed = {(row.object_id, row.version, row.kind) for row in rows}
    seen: set[tuple[str, UUID]] = set()
    for entry in entries:
        ref = entry.ref
        if entry.kind != "prerequisite_method_scope":
            key = (entry.kind, ref.object_id)
            if key in seen:
                # 同类对象重复关联，去重校验失败。
                raise relationship_error(entry.path, "同一对象不能重复关联。")
            seen.add(key)
        if entry.kind == "task_prerequisite" and ref.object_id == owner_id:
            raise relationship_error(entry.path, "任务不能把自身作为先导。", "dependency_cycle")
        if (ref.object_id, ref.version, ref.kind) not in allowed:
            raise relationship_error(entry.path, "引用的版本不存在、已移除或不属于本领域。")

    if isinstance(content, TaskDefinition) and content.prerequisites:
        # 已提交快照各自无环；沿新边递归查是否回到本任务。
        cycle = await connection.scalar(
            text(
                "WITH RECURSIVE edges(object_id,version) AS ("
                f"{_EXACT_REFS} UNION "
                "SELECT r.target_id,r.target_version FROM edges e JOIN domain.object_reference r "
                "ON (r.owner_id,r.owner_version)=(e.object_id,e.version) "
                "WHERE r.relation_kind='task_prerequisite'"
                ") SELECT EXISTS(SELECT 1 FROM edges WHERE object_id=:owner)"
            ),
            {"owner": owner_id, **_keys([link.task_ref for link in content.prerequisites])},
        )
        if cycle:
            # 递归路径回到本任务，构成先导环。
            raise relationship_error(
                "/prerequisites", "先导路径回到了当前任务。", "dependency_cycle"
            )


async def apply_references(
    connection: AsyncConnection, owner: MemberRef, content: DefinitionContent
) -> None:
    entries = references(content)
    if entries:
        # 逐条落库对象间关系索引。
        await connection.execute(
            _RELATION_INSERT,
            [
                {
                    "owner": owner.object_id,
                    "owner_version": owner.version,
                    "path": entry.path,
                    "relation_kind": entry.kind,
                    "target": entry.ref.object_id,
                    "target_version": entry.ref.version,
                }
                for entry in entries
            ],
        )


async def method_knowledge(
    connection: AsyncConnection, methods: list[SolutionRef]
) -> tuple[list[KnowledgeRef], list[KnowledgeSources]]:
    """只按精确方法版本读取直接KC，保留每个来源的实际版本。"""
    if not methods:
        return [], []  # 无方法则无直接知识成分
    rows = await connection.execute(
        text(
            f"WITH selected AS ({_EXACT_REFS}) "
            "SELECT r.owner_id,r.owner_version,r.target_id,r.target_version FROM selected s "
            "JOIN domain.object_reference r ON "
            "(r.owner_id,r.owner_version)=(s.object_id,s.version) "
            "WHERE r.relation_kind='solution_kc' "
            "ORDER BY r.owner_id,r.path"
        ),
        _keys(methods),
    )
    refs: dict[tuple[UUID, int], KnowledgeRef] = {}
    uses: dict[UUID, list[KnowledgeUse]] = {}
    for row in rows:
        # 按知识成分聚合来源方法，保留方法实际版本。
        kc = KnowledgeRef(kind="kc", object_id=row.target_id, version=row.target_version)
        method = SolutionRef(kind="solution", object_id=row.owner_id, version=row.owner_version)
        refs[(kc.object_id, kc.version)] = kc
        uses.setdefault(kc.object_id, []).append(KnowledgeUse(method_ref=method, kc_ref=kc))
    return list(refs.values()), [
        KnowledgeSources(kc_id=kc_id, uses=sources) for kc_id, sources in uses.items()
    ]
