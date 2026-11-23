"""各模块在此声明事件订阅，Worker 注入实际处理器。"""

from collections.abc import Awaitable, Callable

from deermind.abstractions.delivery import Acceptance, EventNotice
from deermind.abstractions.material_intake import DELETED, RECEIVED, REJECTED, REQUESTED
from deermind.abstractions.task_supply import REQUESTED as SUPPLY_REQUESTED
from deermind.bootstrap.executions import registry
from deermind.bootstrap.waits import policies
from deermind.foundation.system.delivery.contracts import Subscription, SubscriptionRegistry
from deermind.foundation.system.executions.contracts import Registry
from deermind.foundation.system.waits.notifications import subscription
from deermind.spaces.evaluation.goal_results import TRIGGER
from sqlalchemy.ext.asyncio import AsyncConnection

type Handler = Callable[[AsyncConnection, EventNotice], Awaitable[Acceptance]]


async def _unbound(_connection: AsyncConnection, _notice: EventNotice) -> Acceptance:
    raise RuntimeError("Business delivery requires the Worker composition")


def subscriptions(
    receive_intake: Handler = _unbound,
    receive_result: Handler = _unbound,
    invalidate_source: Handler = _unbound,
    reassess_target: Handler = _unbound,
    supply_task: Handler = _unbound,
    *,
    entries: Registry | None = None,
) -> SubscriptionRegistry:
    waiting = subscription(entries or registry(), policies())
    scope = frozenset({"material_import"})
    items = [
        Subscription(
            "domain_task_supply",
            "1",
            frozenset({SUPPLY_REQUESTED}),
            frozenset({"learning_space"}),
            supply_task,
        ),
        Subscription(
            "evaluation_reassess_target",
            "1",
            frozenset({TRIGGER}),
            frozenset({"learning_space"}),
            reassess_target,
        ),
        Subscription("domain_intake", "1", frozenset({REQUESTED}), scope, receive_intake),
        Subscription(
            "domain_material_invalidation", "1", frozenset({DELETED}), scope, invalidate_source
        ),
        Subscription(
            "product_intake_result", "1", frozenset({RECEIVED, REJECTED}), scope, receive_result
        ),
    ]
    return SubscriptionRegistry([*items, waiting] if waiting else items)
