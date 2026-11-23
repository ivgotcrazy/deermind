"""Domain 对已保存的题目执行固定任务、方法和接触条件筛选。"""

from collections.abc import Iterable
from dataclasses import dataclass

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.task_supply import TaskSupplyRequested, UnfilledSupply
from deermind.spaces.domain.public import InstanceView, ReferenceSolution


@dataclass(frozen=True)
class EligibleInstance:
    instance: InstanceView
    references: tuple[ReferenceSolution, ...]


def select_instances(
    requested: TaskSupplyRequested, instances: Iterable[InstanceView]
) -> tuple[list[EligibleInstance], UnfilledSupply | None]:
    """只交付条件已能判定的题。自然语言范围尚未核实时保留缺口。"""
    if requested.exposed_instances is None:
        return [], UnfilledSupply(
            count=requested.count,
            condition=requested.assessment_constraints,
            reason="exposure_unknown",
            retryable=False,
        )
    if requested.assessment_constraints and requested.assessment_constraints.strip():
        return [], UnfilledSupply(
            count=requested.count,
            condition=requested.assessment_constraints,
            reason="requires_semantic_check",
            retryable=True,
        )
    exposed = {value.id for value in requested.exposed_instances}
    allowed = set((reference.id, reference.version) for reference in requested.allowed_method_refs)
    seen: set[str] = set()
    chosen: list[EligibleInstance] = []
    for instance in instances:
        reference, body = instance.instance_ref, instance.content
        if (
            instance.is_deleted
            or str(reference.object_id) in exposed
            or str(body.task_ref.object_id) != requested.task_ref.id
            or body.task_ref.version != requested.task_ref.version
        ):
            continue
        matches = tuple(
            item
            for item in body.reference_solutions
            if (str(item.solution_ref.object_id), item.solution_ref.version) in allowed
        )
        if not matches or (requested.purpose == "assessment" and body.answer_basis is None):
            continue
        statement = canonical_json(body.statement.model_dump(mode="json"))
        if statement in seen:
            continue
        seen.add(statement)
        chosen.append(EligibleInstance(instance, matches))
        if len(chosen) == requested.count:
            return chosen, None
    return chosen, UnfilledSupply(
        count=requested.count - len(chosen),
        condition=requested.assessment_constraints,
        reason="no_eligible_instance",
        retryable=True,
    )
