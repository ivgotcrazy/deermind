"""学习助手等待 Domain 对本次供题请求保存的批次。"""

from collections.abc import Awaitable, Callable
from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Execution
from deermind.abstractions.task_supply import COMPLETED
from deermind.abstractions.waits import Condition, Match, Wait
from deermind.foundation.system.waits.contracts import Policy
from sqlalchemy.ext.asyncio import AsyncConnection

PROBE = Ref(owner="interaction", type="wait_policy", id="task_supply", revision=1)


def policy(find: Callable[[AsyncConnection, UUID, UUID], Awaitable[Match | None]]) -> Policy:
    async def probe(db: AsyncConnection, work: Execution, condition: Condition) -> Match | None:
        if condition.equals.get("producer") != "domain":
            raise ValueError("Supply wait must identify its producer")
        return await find(db, work.scope_id, UUID(condition.equals["correlation_id"]))

    async def handle(_db: AsyncConnection, _work: Execution, wait: Wait) -> Ref:
        if wait.result_ref:
            return wait.result_ref
        return Ref(owner="interaction", type="task_supply_timeout", id=str(wait.wait_id))

    return Policy(
        PROBE,
        frozenset({COMPLETED}),
        frozenset({"learning_space"}),
        "interaction.use_supplied_task",
        "interaction.supply_timed_out",
        probe,
        handle,
    )
