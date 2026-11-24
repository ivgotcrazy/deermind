"""在已确认的题单上顺序打开正式检测轮。"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, Ref
from deermind.foundation.system.public.errors import RequestError
from deermind.product.public.authentication import AccountView
from deermind.spaces.domain.public import TaskInstance
from deermind.spaces.interaction import conversation_facts as facts
from deermind.spaces.interaction import detection_plans, history, round_facts, task_facts
from deermind.spaces.interaction.conversation import (
    Conversation,
    activity_change,
    assign_message,
    draft,
    lock_position,
    message_event,
    next_position,
    ref,
    revise,
    store_position,
)
from deermind.spaces.interaction.public import (
    CONTROL_ACTIVITY,
    ActivityControlReceipt,
    ActivityControlResult,
    OpenDetectionRound,
    QuestionPart,
)
from deermind.spaces.interaction.student_context import ActivityConfig, ReadQuestion
from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class OpenedRound:
    events: list[EventDraft]
    input_id: UUID
    message_id: UUID
    round_ref: Ref
    activity_ref: Ref


class DetectionRounds:
    def __init__(
        self,
        conversation: Conversation,
        activity_config: ActivityConfig,
        read_question: ReadQuestion,
    ) -> None:
        self.conversation = conversation
        self.activity_config = activity_config
        self.read_question = read_question

    async def open(
        self,
        account: AccountView,
        scope: UUID,
        command: OpenDetectionRound,
    ) -> ActivityControlReceipt:
        service = self.conversation
        principal = account.account_id
        async with service.engine.begin() as db:
            await service.authorize(db, account, scope, False)
            receipt = await service.receipts.claim_request(
                db,
                principal_id=str(principal),
                action=CONTROL_ACTIVITY,
                scope_id=str(scope),
                request_id=command.request_id,
                normalized_input=command.model_dump(mode="json", exclude={"request_id"}),
            )
            if receipt.result_ref:
                return await service.replay_control(scope, receipt)
            adoption = await service.authorize(db, account, scope, True)
            await lock_position(db, scope)
            current = await history.current(db, scope)
            if current.active_input_id:
                raise RequestError(409, "interaction_busy", "正在处理上一条，请稍候。")
            leaf = current.current_activity
            if (
                leaf is None
                or leaf.type != "detection"
                or leaf.run_state != "active"
                or leaf.activity_ref != command.activity_ref
                or leaf.activity_ref.revision != command.expected_activity_revision
            ):
                raise RequestError(409, "revision_conflict", "当前检测活动已变化。")
            state = await history.activity_at(db, scope, leaf.activity_ref.activity_id)
            config, _course = await self.activity_config(
                scope,
                state.identity.adoption_ref,
                "detection",
                state.identity.config_ref,
            )
            if not config or not any(
                node.node_id == leaf.node_id and command.action in node.allowed_actions
                for node in config.definition.blueprint.nodes
            ):
                raise RequestError(409, "blocked", "当前蓝图节点尚不能开始这一轮。")
            plan = await self._plan(db, scope, leaf.activity_ref.activity_id, command)
            if plan.adoption_ref != UUID(adoption.adoption_ref.id):
                raise RequestError(409, "stale_plan", "学习目标已更新，请重新准备题单。")
            if command.action == "start_detection":
                if plan.status != "prepared" or current.current_round is not None:
                    raise RequestError(409, "stale_plan", "该题单已确认。")
            elif (
                plan.status != "confirmed"
                or current.current_round is None
                or not current.current_round.can_continue
            ):
                raise RequestError(409, "blocked", "请先结束当前检测轮。")
            used = set(
                (
                    await db.scalars(
                        text(
                            "SELECT item_id FROM interaction.detection_rounds "
                            "WHERE plan_id=:id AND plan_revision=:version"
                        ),
                        {"id": command.plan_ref.plan_id, "version": command.plan_ref.revision},
                    )
                ).all()
            )
            items = [
                detection_plans.PlanItem.model_validate_json(canonical_json(item))
                for item in plan.items
            ]
            selected = next((item for item in items if item.item_id not in used), None)
            if selected is None:
                raise RequestError(409, "stale_plan", "题单已完成。")
            task = await self.read_question(db, selected.supplied.task_instance_ref)
            if task is None or task.task_ref != selected.requirement.task_ref:
                raise RequestError(409, "stale_plan", "题目不可用，请重新准备题单。")
            exposed = await db.scalar(
                text(
                    "SELECT 1 FROM interaction.task_uses WHERE scope_id=:scope "
                    "AND instance_ref->>'id'=:id LIMIT 1"
                ),
                {"scope": scope, "id": selected.supplied.task_instance_ref.id},
            )
            if exposed:
                raise RequestError(409, "stale_plan", "该题已使用，请重新准备题单。")
            sequence, epoch = await next_position(db, scope)
            opened = self._drafts(
                scope,
                command,
                state,
                selected,
                task,
                adoption.adoption_ref,
                plan.confirmed_by_input,
                sequence,
                epoch + 1,
            )
            await service.append(db, scope, principal, receipt.request_ref, opened.events)
            await store_position(db, scope, leaf.activity_ref.activity_id, sequence, epoch + 1)
            result = ActivityControlResult(
                current=await history.current(db, scope),
                outcome="changed",
                committed_refs=[
                    opened.round_ref,
                    opened.activity_ref,
                    ref("message", opened.message_id),
                ],
            )
            return await service.save_control_result(
                db,
                scope,
                principal,
                receipt,
                opened.input_id,
                command.request_id,
                result,
                [ref("message", opened.message_id)],
                [opened.activity_ref],
            )

    @staticmethod
    async def _plan(
        db: AsyncConnection,
        scope: UUID,
        activity: UUID,
        command: OpenDetectionRound,
    ) -> Row[tuple[UUID, list[object], str, UUID | None]]:
        fixed = command.plan_ref
        row = (
            await db.execute(
                text(
                    "SELECT v.adoption_ref,v.items,p.status,p.confirmed_by_input "
                    "FROM interaction.detection_plans h "
                    "JOIN interaction.plan_revisions v USING(plan_id) "
                    "JOIN interaction.plan_progress p "
                    "ON (p.plan_id,p.plan_revision)=(v.plan_id,v.revision) "
                    "WHERE h.scope_id=:scope AND h.activity_id=:activity AND v.plan_id=:id "
                    "AND v.revision=:revision AND NOT EXISTS ("
                    "SELECT 1 FROM interaction.plan_revisions newer "
                    "WHERE newer.plan_id=v.plan_id AND newer.revision>v.revision) FOR UPDATE OF p"
                ),
                {
                    "scope": scope,
                    "activity": activity,
                    "id": fixed.plan_id,
                    "revision": fixed.revision,
                },
            )
        ).one_or_none()
        if row is None:
            raise RequestError(409, "stale_plan", "找不到当前题单版本，请重新准备。")
        return row

    @staticmethod
    def _drafts(
        scope: UUID,
        command: OpenDetectionRound,
        active: history.ActivityState,
        selected: detection_plans.PlanItem,
        task: TaskInstance,
        adoption: Ref,
        confirmed: UUID | None,
        seq: int,
        epoch: int,
    ) -> OpenedRound:
        now = datetime.now(UTC)
        input_id, message_id, round_id, use_id = uuid4(), uuid4(), uuid4(), uuid4()
        activity = command.activity_ref.activity_id
        input_ref, task_ref, round_ref = (
            ref("input", input_id),
            ref("task_use", use_id),
            ref("round", round_id, 1),
        )
        change = revise(
            active.position,
            "active",
            active.position.node_id,
            command.action,
            now,
            input_id=input_id,
        )
        change = change.model_copy(update={"related_round_ref": round_ref})
        activity_ref = ref("activity", activity, change.revision)
        plan = command.plan_ref
        plan_ref = ref("detection_plan", plan.plan_id, plan.revision)
        input_row = facts.InputFact(
            input_id=input_id,
            scope_id=scope,
            request_id=command.request_id,
            kind="activity_control",
            input=command.model_dump(mode="json"),
            turn_epoch=epoch,
            accepted_at=now,
        )
        accepted = draft(
            scope,
            facts.ACCEPTED,
            input_ref,
            facts.InputAccepted(
                input_ref=input_ref,
                adoption_ref=adoption,
                records=[facts.record(facts.INPUT, input_id, input_row)],
            ),
            command.request_id,
        )
        message = facts.MessageFact(
            message_id=message_id,
            scope_id=scope,
            message_seq=seq,
            role="assistant",
            parts=[
                QuestionPart(
                    part_id="question",
                    type="question",
                    title=task.title,
                    purpose="detection",
                    task_use_ref=task_ref,
                    statement=task.statement,
                )
            ],
            source_input_ref=input_id,
            source_trigger_ref=None,
            committed_at=now,
        )
        use = task_facts.TaskUseFact(
            task_use_id=use_id,
            scope_id=scope,
            activity_id=activity,
            round_id=round_id,
            plan_item_ref=plan_ref.model_copy(update={"path": "/items/" + selected.item_id}),
            instance_ref=selected.supplied.task_instance_ref,
            statement=task.statement.model_dump(mode="json"),
            adoption_ref=UUID(adoption.id),
            purpose="detection",
            method_conditions=selected.requirement.model_dump(mode="json"),
            prepared_at=now,
            provided_message_ref=message_id,
        )
        case = round_facts.Round(
            round_id=round_id,
            activity_id=activity,
            plan_id=plan.plan_id,
            plan_revision=plan.revision,
            item_id=selected.item_id,
            task_use_ref=use_id,
            opened_at=now,
        )
        state = round_facts.RoundRevision(
            round_id=round_id,
            revision=1,
            state="open",
            reason=command.action,
            source_input_ref=input_id,
            source_trigger_ref=None,
            submission_ref=None,
            created_at=now,
        )
        next_step = detection_plans.PlanProgress(
            plan_id=plan.plan_id,
            plan_revision=plan.revision,
            confirmed_by_input=confirmed or input_id,
            status="confirmed",
            cancelled_items=[],
            current_round_ref=round_id,
        )
        task_created = draft(
            scope,
            task_facts.PRESENTED,
            task_ref,
            task_facts.TaskUseCreated(
                task_use_ref=task_ref,
                activity_ref=activity_ref,
                plan_ref=plan_ref,
                round_ref=round_ref,
                adoption_ref=adoption,
                records=[facts.record(task_facts.TASK_USE, use_id, use)],
            ),
            command.request_id,
        )
        started = draft(
            scope,
            round_facts.STARTED,
            round_ref,
            round_facts.RoundStarted(
                round_ref=round_ref,
                activity_ref=activity_ref,
                plan_ref=plan,
                task_use_ref=task_ref,
                source_input_ref=input_ref,
                records=[
                    facts.record(round_facts.ROUND, round_id, case),
                    facts.record(round_facts.REVISION, f"{round_id}:1", state),
                    facts.record(
                        detection_plans.PROGRESS, f"{plan.plan_id}:{plan.revision}", next_step
                    ),
                ],
            ),
            command.request_id,
        )
        shown = [
            message_event(message, activity, command.request_id),
            assign_message(message, activity, command.request_id),
        ]
        activity_event = activity_change(active.identity, change, command.request_id)
        return OpenedRound(
            [accepted, activity_event, *shown, task_created, started],
            input_id,
            message_id,
            round_ref,
            activity_ref,
        )
