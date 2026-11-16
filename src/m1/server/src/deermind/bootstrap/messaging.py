"""当前增量只装配交接底座；业务订阅随所属模块实现，不生成假工作。"""

from deermind.foundation.system.delivery.contracts import SubscriptionRegistry


def subscriptions() -> SubscriptionRegistry:
    return SubscriptionRegistry([])
