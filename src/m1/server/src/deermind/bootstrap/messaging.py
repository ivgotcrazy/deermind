"""当前增量只装配交接底座；业务订阅随所属模块实现，不生成假工作。"""

from deermind.bootstrap.executions import registry
from deermind.bootstrap.waits import policies
from deermind.foundation.system.delivery.contracts import SubscriptionRegistry
from deermind.foundation.system.waits.notifications import subscription


def subscriptions() -> SubscriptionRegistry:
    waiting = subscription(registry(), policies())
    return SubscriptionRegistry([waiting] if waiting else [])
