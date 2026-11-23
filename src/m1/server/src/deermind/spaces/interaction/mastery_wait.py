"""Wait for the publication of the exact answer needed by a follow-up."""

from collections.abc import Awaitable, Callable
from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Execution
from deermind.abstractions.waits import Condition, Match, Wait
from deermind.foundation.system.waits.contracts import Policy
from sqlalchemy.ext.asyncio import AsyncConnection

EVENT = "BeliefEvaluationCompleted"
PROBE = Ref(owner="interaction", type="wait_policy", id="answer_mastery", revision=1)


def policy(find: Callable[[AsyncConnection, UUID, UUID], Awaitable[Match | None]]) -> Policy:
    async def probe(db: AsyncConnection, work: Execution, condition: Condition) -> Match | None:
        key = condition.result_key
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
