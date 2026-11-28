"""Validate the authoring graph and freeze edition-local Domain definitions."""

from graphlib import CycleError, TopologicalSorter
from uuid import UUID, uuid5

from deermind.foundation.system.public.errors import RequestError
from deermind.product.public.material_editions import ContentNode, MapTask, TeachingModel
from deermind.spaces.domain.public import (
    ConfirmKCPathRequest,
    DefinitionContent,
    KnowledgeComponent,
    KnowledgeRef,
    MemberRef,
    MethodDependency,
    Prerequisite,
    SolutionDefinition,
    SolutionRef,
    TaskDefinition,
    TaskRef,
    paragraph,
)


def invalid(message: str) -> RequestError:
    return RequestError(422, "invalid_teaching", message)


def validate_model(model: TeachingModel, nodes: list[ContentNode]) -> list[str]:
    tasks = {t.key: t for t in model.tasks}
    knowledge = {k.key for k in model.knowledge}
    if len(tasks) != len(model.tasks) or len(knowledge) != len(model.knowledge):
        raise invalid("同版任务或知识标识重复。")
    paired: set[str] = set()
    edges: dict[str, set[str]] = {}
    sections = {n.node_id for n in nodes if n.node_kind in {"section", "chapter", "unit"}}
    parents = {n.node_id: n.parent_id for n in nodes}
    for task in tasks.values():
        key = task.knowledge_key
        if task.task_type == "knowledge":
            if key not in knowledge or not key or key in paired:
                raise invalid(f"《{task.name}》须单独对应本版的一个知识。")
            paired.add(key)
        elif key is not None:
            raise invalid(f"综合任务《{task.name}》不能绑定知识。")
        if task.chapter_id not in sections:
            raise invalid(f"《{task.name}》的章节不存在。")
        for source in task.source_nodes:
            cursor: UUID | None = source
            while cursor is not None and cursor != task.chapter_id:
                cursor = parents.get(cursor)
            if cursor is None:
                raise invalid(f"《{task.name}》的原文来源不属于所选章节。")
        edges[task.key] = set()
        if len({m.key for m in task.methods}) != len(task.methods):
            raise invalid(f"《{task.name}》的方法标识重复。")
        for method in task.methods:
            seen: set[str] = set()
            for dep in method.dependencies:
                target = tasks.get(dep.task_key)
                if not target or target == task or target.key in seen:
                    raise invalid(f"《{task.name}》的「{method.name}」引用了缺失、重复或自身任务。")
                if task.task_type == "knowledge" and target.task_type != "knowledge":
                    raise invalid(f"《{task.name}》的「{method.name}」只能依赖知识任务。")
                seen.add(target.key)
            edges[task.key].update(seen)
    if paired != knowledge:
        raise invalid("每个知识都须有唯一的知识任务。")
    try:
        return list(TopologicalSorter(edges).static_order())
    except CycleError as exc:
        chain = " → ".join(tasks[k].name for k in exc.args[1])
        raise invalid(f"前置任务形成循环：{chain}") from exc


def build_teaching(
    edition: UUID, model: TeachingModel, nodes: list[ContentNode]
) -> tuple[list[MapTask], list[tuple[MemberRef, DefinitionContent]], list[ConfirmKCPathRequest]]:
    order = validate_model(model, nodes)
    if not order:
        raise invalid("请先添加教学任务。")
    tasks = {t.key: t for t in model.tasks}
    concepts = {k.key: k for k in model.knowledge}
    refs = {
        key: TaskRef(kind="task", object_id=uuid5(edition, "task:" + key), version=1)
        for key in order
    }
    kcs = {
        key: KnowledgeRef(kind="kc", object_id=uuid5(edition, "kc:" + key), version=1)
        for key in concepts
    }
    members: list[tuple[MemberRef, DefinitionContent]] = []
    entries: list[MapTask] = []
    paths: list[ConfirmKCPathRequest] = []
    for key, concept in concepts.items():
        if not concept.meaning.strip() or not concept.applicability.strip():
            raise invalid(f"请补充知识《{concept.name}》的含义和适用条件。")
        members.append(
            (
                kcs[key],
                KnowledgeComponent(
                    name=concept.name,
                    definition=paragraph(concept.meaning, "definition"),
                    applicability=paragraph(concept.applicability, "definition"),
                ),
            )
        )
    for key in order:
        task = tasks[key]
        if (
            not task.methods
            or not task.source_nodes
            or not all(
                x.strip()
                for x in (task.description, task.expected_output, task.completion_conditions)
            )
        ):
            raise invalid(f"请补全《{task.name}》的来源、任务说明、预期产出、完成条件和方法。")
        ref = refs[key]
        direct = kcs[task.knowledge_key] if task.knowledge_key else None
        methods: list[SolutionRef] = []
        uses: dict[str, list[SolutionRef]] = {}
        reasons: dict[str, list[str]] = {}
        method_kcs: list[list[KnowledgeRef]] = []
        relevant = [task.knowledge_key] if task.knowledge_key else []
        for m in task.methods:
            if not all(x.strip() for x in (m.steps, m.rationale, m.applicability)):
                raise invalid(f"请补全《{task.name}》方法「{m.name}」的步骤、依据和适用条件。")
            method = SolutionRef(kind="solution", object_id=uuid5(ref.object_id, m.key), version=1)
            methods.append(method)
            deps: list[MethodDependency] = []
            used: list[KnowledgeRef] = []
            for d in m.dependencies:
                deps.append(MethodDependency(task_ref=refs[d.task_key], reason=d.reason))
                uses.setdefault(d.task_key, []).append(method)
                reasons.setdefault(d.task_key, []).append(d.reason)
                k = tasks[d.task_key].knowledge_key
                if k:
                    used.append(kcs[k])
                    if k not in relevant:
                        relevant.append(k)
            method_kcs.append(used)
            members.append(
                (
                    method,
                    SolutionDefinition(
                        name=m.name,
                        approach=paragraph(m.steps, "definition"),
                        key_process=paragraph(m.steps, "definition"),
                        rationale=paragraph(m.rationale, "definition"),
                        applicability=paragraph(m.applicability, "definition"),
                        dependencies=deps,
                    ),
                )
            )
            if direct:
                if not task.insufficient_example.strip():
                    raise invalid(f"请补充《{task.name}》的证据不足示例。")
                paths.append(
                    ConfirmKCPathRequest(
                        request_id=str(edition),
                        task_ref=ref,
                        solution_ref=method,
                        kc_ref=direct,
                        observable_behavior=task.expected_output,
                        insufficient_examples=[task.insufficient_example],
                    )
                )
        union = [
            Prerequisite(
                task_ref=refs[k],
                reason="；".join(dict.fromkeys(reasons[k])),
                applies_to="specified",
                method_refs=which,
            )
            for k, which in uses.items()
        ]
        members.append(
            (
                ref,
                TaskDefinition(
                    name=task.name,
                    task_type=task.task_type,
                    knowledge_ref=direct,
                    responsibility=paragraph(task.description, "definition"),
                    expected_output=paragraph(task.expected_output, "definition"),
                    completion_conditions=paragraph(task.completion_conditions, "definition"),
                    method_refs=methods,
                    prerequisites=union,
                ),
            )
        )
        entries.append(
            MapTask(
                chapter_id=task.chapter_id,
                task_ref=ref,
                name=task.name,
                method_refs=methods,
                method_names=[m.name for m in task.methods],
                method_knowledge=method_kcs,
                knowledge=[kcs[k] for k in relevant],
                knowledge_names=[concepts[k].name for k in relevant],
                prerequisites=union,
                source_nodes=task.source_nodes,
            )
        )
    return entries, members, paths
