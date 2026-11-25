"""各模块在此声明事件订阅，Worker 注入实际处理器。"""

from collections.abc import Awaitable, Callable

from deermind.abstractions.delivery import Acceptance, EventNotice
from deermind.abstractions.material_intake import DELETED, RECEIVED, REJECTED, REQUESTED
from deermind.abstractions.task_supply import REQUESTED as SUPPLY_REQUESTED
from deermind.bootstrap.executions import registry
from deermind.bootstrap.waits import policies
from deermind.foundation.system.delivery.contracts import Subscription, SubscriptionRegistry
from deermind.foundation.system.executions.contracts import Registry
from deermind.foundation.system.waits.contracts import Policies
from deermind.foundation.system.waits.notifications import subscription
from deermind.spaces.evaluation.goal_results import TRIGGER
from deermind.spaces.evaluation.mastery_facts import COMPLETED as MASTERY_COMPLETED
from deermind.spaces.evaluation.operations import ANSWER, TEACHING
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
    receive_evaluation: Handler = _unbound,
    *,
    entries: Registry | None = None,
) -> SubscriptionRegistry:
    shared = entries or registry()
    scope = frozenset({"material_import"})
    items = [
        Subscription(
            "evaluation_submission",
            "1",
            frozenset({ANSWER}),
            frozenset({"learning_space"}),
            receive_evaluation,
        ),
        Subscription(
            "evaluation_teaching",
            "1",
            frozenset({TEACHING}),
            frozenset({"learning_space"}),
            receive_evaluation,
        ),
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
        Subscription(
            "evaluation_goal_from_mastery",
            "1",
            frozenset({MASTERY_COMPLETED}),
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
    # 逐条等待策略接线对应通知订阅。
    for waiting_policy in policies().items:
        subscriber_id = (
            "runtime_waits"
            if waiting_policy.ref.id == "task_supply"
            else f"interaction_wait_{waiting_policy.ref.id}"
        )
        waiting = subscription(shared, Policies([waiting_policy]), subscriber_id)
        if waiting is not None:
            # 策略产生有效订阅才加入注册表。
            items.append(waiting)
    return SubscriptionRegistry(items)
