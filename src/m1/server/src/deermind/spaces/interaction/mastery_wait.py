"""Wait for the publication of the exact answer needed by a follow-up."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from deermind.abstractions.events import FactModel, Ref
from deermind.abstractions.executions import Execution, RunInput
from deermind.abstractions.waits import Condition, Match, ResultKey, Wait, WaitCall
from deermind.foundation.system.executions import store
from deermind.foundation.system.executions.contracts import Registry
from deermind.foundation.system.waits.contracts import Policy
from deermind.foundation.system.waits.service import Waits
from deermind.spaces.interaction import history
from deermind.spaces.interaction.conversation import SCOPE, Conversation
from deermind.spaces.interaction.student_context import ReadQuestion, StudentContext
from deermind.spaces.interaction.turn_result import Reply, complete_turn
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

if TYPE_CHECKING:
    from deermind.spaces.interaction.turn_requests import SpaceAdoption

EVENT = "BeliefEvaluationCompleted"
PROBE = Ref(owner="interaction", type="wait_policy", id="answer_mastery", revision=1)


def policy(find: Callable[[AsyncConnection, UUID, UUID], Awaitable[Match | None]]) -> Policy:
    async def probe(db: AsyncConnection, work: Execution, condition: Condition) -> Match | None:
        key = condition.result_key
        # 等待结果必须是本空间 evaluation 产出的信念结果。
        if key is None or (key.producer, key.result_kind, key.scope_id) != (
            "evaluation",
            "belief_result",
            work.scope_id,
        ):
            raise ValueError("The mastery wait requires a result for this space")
        return await find(db, work.scope_id, key.trigger_event_id)

    async def handle(_db: AsyncConnection, _work: Execution, wait: Wait) -> Ref:
        return wait.result_ref or Ref(
            owner="interaction", type="evaluation_timeout", id=str(wait.wait_id)
        )

    return Policy(
        PROBE,
        frozenset({EVENT}),
        frozenset({"learning_space"}),
        "interaction.use_answer_mastery",
        "interaction.evaluation_timed_out",
        probe,
        handle,
    )


class MasteryFollowUp(FactModel):
    waiting: WaitCall
    adoption_id: UUID
    activity_id: UUID
    round_id: UUID


async def wait_for_mastery(
    conversation: Conversation,
    registry: Registry,
    current_adoption: SpaceAdoption,
    run: RunInput,
    waits: Waits,
) -> MasteryFollowUp | None:
    async with conversation.engine.begin() as db:
        work = await store.active(db, registry, run, "step")
        current = await history.current(db, work.scope_id)
        round_ = current.current_round
        activity = current.current_activity
        # 仅当轮次已关闭且不可继续时，才需要等待掌握结果做后续跟进。
        if not activity or not round_ or round_.state != "closed" or round_.can_continue:
            return None
        trigger = await db.scalar(
            text("""
            SELECT event_ref FROM interaction.submissions
            WHERE scope_id=:scope AND round_id=:round
        """),
            {"scope": work.scope_id, "round": UUID(round_.round_ref.id)},
        )
        # 未取到触发事件引用，无法登记等待。
        if not isinstance(trigger, UUID):
            return None
        adoption = await current_adoption(db, work.scope_id, False)
        active = await history.activity_at(db, work.scope_id, activity.activity_ref.activity_id)
        now = await db.scalar(text("SELECT clock_timestamp()"))
        reserve = 120
        expires = min(now + timedelta(seconds=45), run.deadline_at - timedelta(seconds=reserve))
        # 活动采用与当前采用不符，或剩余时间不足以等待，放弃登记。
        if active.identity.adoption_ref != adoption or expires <= now:
            return None
        waiting = await waits.register(
            db,
            run,
            step_key="answer_mastery",
            owner=round_.round_ref,
            condition=Condition(
                event_types=[EVENT],
                scope_kind=SCOPE,
                scope_id=work.scope_id,
                equals={"producer": "evaluation", "correlation_id": str(trigger)},
                result_key=ResultKey(
                    scope_id=work.scope_id,
                    trigger_event_id=trigger,
                    producer="evaluation",
                    result_kind="belief_result",
                ),
            ),
            probe_ref=PROBE,
            deadline=expires,
            reserve_seconds=reserve,
        )
        return MasteryFollowUp(
            waiting=WaitCall(run=run, wait_id=waiting.wait_id),
            adoption_id=adoption,
            activity_id=activity.activity_ref.activity_id,
            round_id=UUID(round_.round_ref.id),
        )


async def follow_up_context(
    context: StudentContext,
    current_adoption: SpaceAdoption,
    saved: MasteryFollowUp,
    reference: Ref,
    question: ReadQuestion,
) -> str:
    async with context.engine.begin() as db:
        work = await store.active(db, context.registry, saved.waiting.run, "step")
        # 跟进上下文所属轮次已变化，不沿用旧掌握上下文。
        if not await _same_mastery_round(current_adoption, db, work.scope_id, saved):
            return ""
    return await context.build(saved.waiting.run, question, post_close=True, mastery_ref=reference)


async def _same_mastery_round(
    current_adoption: SpaceAdoption, db: AsyncConnection, scope: UUID, saved: MasteryFollowUp
) -> bool:
    current = await history.current(db, scope)
    activity, round_ = current.current_activity, current.current_round
    return (
        await current_adoption(db, scope, False) == saved.adoption_id
        and activity is not None
        and activity.activity_ref.activity_id == saved.activity_id
        and round_ is not None
        and round_.round_ref.id == str(saved.round_id)
        and round_.state == "closed"
        and not round_.can_continue
    )


async def complete_mastery_follow_up(
    conversation: Conversation,
    registry: Registry,
    current_adoption: SpaceAdoption,
    saved: MasteryFollowUp,
    wording: str | None,
) -> None:
    run = saved.waiting.run
    async with conversation.engine.begin() as db:
        work = await store.lock_owned(db, registry, run.execution_id)
        # 已完成且仍是本次尝试，幂等返回。
        if work.state == "completed" and work.active_attempt_id == run.attempt_id:
            return
        work = await store.active(db, registry, run, "finish")
        # 轮次已变化则提示评价对应旧检测；否则用给定措辞或默认提示收尾。
        if not await _same_mastery_round(current_adoption, db, work.scope_id, saved):
            reply = "这次评价对应之前的检测，当前活动可以继续。"
        else:
            reply = wording or "本轮的掌握情况还在核对，可以继续学习。"
        await complete_turn(conversation, db, registry, run, work, "completed", Reply(reply))
