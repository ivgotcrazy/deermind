"""准备固定题单，然后把控制权交还给学生。"""

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from deermind.abstractions.events import FactModel, Ref
from deermind.abstractions.executions import RunInput
from deermind.abstractions.task_supply import REQUESTED, SuppliedTask
from deermind.foundation.system.executions import store
from deermind.foundation.system.waits.service import Waits
from deermind.spaces.domain.public import TaskInstance, TaskRef
from deermind.spaces.evaluation.public import ClaimRef
from deermind.spaces.interaction import detection_plans, history
from deermind.spaces.interaction.blueprints import entry_node
from deermind.spaces.interaction.conversation import draft, ref
from deermind.spaces.interaction.public import DetectionPlanPart
from deermind.spaces.interaction.student_turns import StudentTurns
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


class PlanWork(FactModel):
    activity_ref: Ref | None
    adoption: UUID
    groups: list[detection_plans.PlanWait]
    gaps: list[str]


class DetectionPreparation:
    def __init__(
        self,
        student: StudentTurns,
        waits: Waits,
        domain_for: Callable[[AsyncConnection, UUID], Awaitable[UUID]],
        read_task: Callable[[ClaimRef], Awaitable[TaskRef]],
        supplied: Callable[
            [AsyncConnection, UUID, UUID], Awaitable[tuple[TaskInstance, SuppliedTask, UUID] | None]
        ],
    ) -> None:
        self.student, self.waits, self.domain_for = student, waits, domain_for
        self.read_task, self.supplied = read_task, supplied

    async def prepare(self, run: RunInput) -> PlanWork:
        service = self.student
        async with service.engine.connect() as db:
            work = await store.load(db, run.execution_id)
            auth = await store.authorization(db, run.execution_id)
            current = await history.current(db, work.scope_id)
            leaf = current.current_activity
            adoption = UUID(auth.basis_refs[0].id)
            parent = (
                await history.activity_at(db, work.scope_id, leaf.activity_ref.activity_id)
                if leaf
                else None
            )
        failed = PlanWork(
            activity_ref=None, adoption=adoption, groups=[], gaps=["当前活动无法准备检测。"]
        )
        if parent and parent.identity.type != "detection":
            config, _course = await service.activity_config(
                work.scope_id,
                adoption,
                parent.identity.type,
                parent.identity.config_ref,
            )
            if not config or not any(
                node.node_id == parent.position.node_id
                and "prepare_detection" in node.allowed_actions
                for node in config.definition.blueprint.nodes
            ):
                return failed
        config, course = await service.activity_config(work.scope_id, adoption, "detection", None)
        if config is None or config.gaps:
            return failed
        first = entry_node(config.definition.blueprint)
        if first is None:
            return failed
        tasks = {goal.claim_ref: await self.read_task(goal.claim_ref) for goal in course.items}
        required = detection_plans.requirements(course, tasks)
        if not required.items:
            return failed.model_copy(update={"gaps": required.gaps})
        async with service.engine.begin() as db:
            work = await store.active(db, service.registry, run, "step")
            source = (
                await db.execute(
                    text(
                        "SELECT request_id,source_event_id FROM interaction.inputs "
                        "WHERE input_id=:id"
                    ),
                    {"id": UUID(work.input_ref.id)},
                )
            ).one()
            principal = UUID(auth.initiator_ref.id)
            if parent and parent.identity.type == "detection":
                if parent.position.source_input_ref != UUID(work.input_ref.id):
                    return failed
                target = parent.identity.activity_id
                revision = parent.position.revision
            else:
                created = await service.conversation.begin(
                    db,
                    work.scope_id,
                    principal,
                    Ref(owner="product", type="space_adoption", id=str(adoption)),
                    config.config_ref,
                    config.definition,
                    "detection",
                    "准备检测",
                    source.source_event_id,
                    parent_id=parent.identity.activity_id if parent else None,
                    input_id=UUID(work.input_ref.id),
                    initial_node=first.node_id,
                    request_ref=UUID(work.acceptance_key),
                )
                target, revision = created.activity_id, created.revision
            activity = ref("activity", target, revision)
            domain = await self.domain_for(db, work.scope_id)
            rows = (
                await db.execute(
                    text(
                        "SELECT instance_ref,source_event_id FROM interaction.task_uses "
                        "WHERE scope_id=:scope AND instance_ref IS NOT NULL ORDER BY prepared_at"
                    ),
                    {"scope": work.scope_id},
                )
            ).all()
            known = [ref("task_use_event", row.source_event_id) for row in rows]
            exposed = list(dict.fromkeys(Ref.model_validate(row.instance_ref) for row in rows))
            now = datetime.now(UTC)
            groups: list[detection_plans.PlanWait] = []
            for requirement in required.items:
                identity, payload = detection_plans.supply_request(
                    work, activity, domain, requirement, known, exposed
                )
                if not await db.scalar(
                    text("SELECT 1 FROM runtime.events WHERE event_id=:id"), {"id": identity}
                ):
                    event = draft(
                        work.scope_id, REQUESTED, payload.request_ref, payload, source.request_id
                    )
                    await service.conversation.append(
                        db,
                        work.scope_id,
                        principal,
                        UUID(work.acceptance_key),
                        [replace(event, event_id=identity)],
                    )
                groups.append(
                    await detection_plans.register_requirement(
                        db,
                        self.waits,
                        run,
                        work.scope_id,
                        identity,
                        payload,
                        requirement,
                        now,
                    )
                )
            return PlanWork(
                activity_ref=activity, adoption=adoption, groups=groups, gaps=required.gaps
            )

    async def finish(self, run: RunInput, prepared: PlanWork, available: set[UUID]) -> None:
        service = self.student
        async with service.engine.begin() as db:
            current = await store.lock_owned(db, service.registry, run.execution_id)
            if current.state == "completed":
                return
            work = await store.active(db, service.registry, run, "finish")
            source = await db.scalar(
                text("SELECT request_id FROM interaction.inputs WHERE input_id=:id"),
                {"id": UUID(work.input_ref.id)},
            )
            assert isinstance(source, str)
            principal = UUID((await store.authorization(db, run.execution_id)).initiator_ref.id)
            items: list[detection_plans.PlanItem] = []
            gaps = list(prepared.gaps)
            selected: set[Ref] = set()
            for entry in prepared.groups:
                result = (
                    await self.supplied(db, work.scope_id, entry.trigger)
                    if entry.trigger in available
                    else None
                )
                if result is None or result[1].task_instance_ref in selected:
                    gaps.append("暂时没有满足该方法和范围的题目。")
                    continue
                instance, supplied, _event = result
                if instance.task_ref != entry.requirement.task_ref:
                    gaps.append("供题结果与原 Task 不一致。")
                    continue
                selected.add(supplied.task_instance_ref)
                items.append(
                    detection_plans.PlanItem(
                        item_id=str(entry.trigger),
                        title=instance.title,
                        requirement=entry.requirement,
                        supplied=supplied,
                    )
                )
            part = None
            if prepared.activity_ref and items:
                owner, payload = detection_plans.prepared_plan(
                    work, prepared.activity_ref, prepared.adoption, items, gaps
                )
                await service.conversation.append(
                    db,
                    work.scope_id,
                    principal,
                    UUID(work.acceptance_key),
                    [
                        draft(work.scope_id, detection_plans.PREPARED, owner, payload, source),
                    ],
                )
                part = DetectionPlanPart(
                    part_id="detection_plan",
                    type="detection_plan",
                    plan_ref=owner,
                    question_count=len(items),
                    gaps=gaps,
                )
            wording = "题单已准备好，确认后开始。" if part else "暂时没有可用的检测题。"
            await service.save_plan_result(db, run, work, wording, part)
