"""Compose the narrow Product, Domain and Evaluation views for learning tools."""

from collections.abc import Sequence
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import Ref
from deermind.product.learning.course_spaces import CourseSpaces
from deermind.product.public.courses import CourseSnapshot
from deermind.spaces.domain.evaluation_references import read_fixed_reference
from deermind.spaces.domain.public import SolutionRef, TaskInstance
from deermind.spaces.evaluation.goal_results import GoalResults
from deermind.spaces.evaluation.publication import MasteryPublication
from deermind.spaces.interaction.learning_materials import ReadableMaterial
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncConnection

COURSE_LIMIT = 16
STATE_LIMIT = 8


async def read_study_method_name(
    db: AsyncConnection, domain: UUID, method: SolutionRef
) -> str | None:
    """Read the name of a Solution pinned by the adopted learning target."""
    fixed = await read_fixed_reference(
        db,
        domain,
        Ref(owner="domain", type="solution", id=str(method.object_id), version=method.version),
    )
    name = fixed[0].get("name") if fixed else None
    return name if isinstance(name, str) else None


def domain_refs(snapshot: CourseSnapshot) -> list[ReadableMaterial]:
    items: list[ReadableMaterial] = []
    seen: set[tuple[str, UUID, int]] = set()
    for chapter in snapshot.chapters:
        for association in chapter.associations:
            if not association.active:
                continue
            for obj in (association.task_ref, *association.method_refs):
                key = (obj.kind, obj.object_id, obj.version)
                if key in seen:
                    continue
                seen.add(key)
                reference = Ref(
                    owner="domain", type=obj.kind, id=str(obj.object_id), version=obj.version
                )
                label = "任务" if reference.type == "task" else "解法"
                items.append(
                    ReadableMaterial(
                        kind="course", label=f"{chapter.title} · {label}", reference=reference
                    )
                )
    return items


class StudentMaterialSources:
    def __init__(self, spaces: CourseSpaces, publications: MasteryPublication) -> None:
        self.spaces = spaces
        self.publications = publications

    async def catalogue(
        self, db: AsyncConnection, scope: UUID, adoption: UUID, explicit: Sequence[Ref]
    ) -> list[ReadableMaterial]:
        adopted = await self.spaces.fixed_adoption(db, scope, adoption)
        snapshot = adopted.snapshot
        items = domain_refs(snapshot)[: COURSE_LIMIT // 2]
        chapters = sorted(
            snapshot.chapters,
            key=lambda chapter: (
                not any(
                    reference in chapter.content_refs or reference.id == str(chapter.chapter_id)
                    for reference in explicit
                )
            ),
        )
        for chapter in chapters:
            by_priority = sorted(
                enumerate(chapter.content_refs, start=1), key=lambda item: item[1] not in explicit
            )
            for index, reference in by_priority:
                items.append(
                    ReadableMaterial(
                        kind="course",
                        label=f"{chapter.title} · 教材第 {index} 段",
                        reference=reference,
                    )
                )
                if len(items) >= COURSE_LIMIT:
                    break
            if len(items) >= COURSE_LIMIT:
                break
        fixed = await self.publications.current_reference(db, scope)
        goal = await GoalResults.current_reference(db, scope, UUID(adopted.target_basis_ref.id))
        published: list[ReadableMaterial] = []
        for item in snapshot.items:
            if fixed:
                published.append(
                    ReadableMaterial(
                        kind="published",
                        label=f"{item.title} · 掌握状态",
                        reference=fixed.model_copy(update={"path": f"/{item.item_id}"}),
                    )
                )
            if goal:
                published.append(
                    ReadableMaterial(
                        kind="published",
                        label=f"{item.title} · 目标判断",
                        reference=Ref(
                            owner="evaluation",
                            type="goal_evaluation",
                            id=str(goal),
                            path=f"/{item.item_id}",
                        ),
                    )
                )
            if len(published) >= STATE_LIMIT:
                break
        return [*items[:COURSE_LIMIT], *published[:STATE_LIMIT]]

    async def read(
        self, db: AsyncConnection, scope: UUID, adoption: UUID, reference: Ref
    ) -> tuple[JsonValue, list[Ref]] | None:
        adopted = await self.spaces.fixed_adoption(db, scope, adoption)
        if reference.owner == "product" and reference.type == "material_candidate":
            if not any(reference in chapter.content_refs for chapter in adopted.snapshot.chapters):
                return None
            parts = await self.spaces.read_quoted_content(scope, adoption, reference)
            material: list[JsonValue] = [part for part in parts]
            return material, [reference]
        if reference.owner == "domain":
            allowed = [value.reference for value in domain_refs(adopted.snapshot)]
            if reference.type != "task_instance" and reference not in allowed:
                return None
            domain = await self.spaces.domain_for(db, scope)
            record = await read_fixed_reference(db, domain, reference)
            if record is None:
                return None
            body, event = record
            if reference.type == "task_instance":
                instance = TaskInstance.model_validate_json(canonical_json(body))
                task = Ref(
                    owner="domain",
                    type="task",
                    id=str(instance.task_ref.object_id),
                    version=instance.task_ref.version,
                )
                if task not in allowed:
                    return None
            return body, [reference, Ref(owner="domain", type="event", id=str(event))]

        if reference.owner != "evaluation" or reference.path is None:
            return None
        item_id = UUID(reference.path.removeprefix("/"))
        item = next((item for item in adopted.snapshot.items if item.item_id == item_id), None)
        if item is None:
            return None
        fixed = reference.model_copy(update={"path": None})
        if reference.type == "mastery_snapshot":
            return await self.publications.read(scope, [item.claim_ref], fixed), [reference]
        if reference.type == "goal_evaluation":
            goal = await GoalResults.fixed_result(
                db, scope, UUID(adopted.target_basis_ref.id), UUID(reference.id)
            )
            if goal:
                match = next(
                    (entry for entry in goal.result.items if entry.item_id == item_id), None
                )
                if match:
                    return match.model_dump(mode="json"), [reference, adopted.target_basis_ref]
        return None
