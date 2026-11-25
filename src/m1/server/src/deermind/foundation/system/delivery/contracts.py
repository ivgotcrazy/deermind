"""进程内订阅合同及严格通知格式；通知不携带正文或读取授权。

分层定位：foundation（公共运行底座 / 事件交接）
对外契约：Subscription 登记订阅者与事务回调；SubscriptionRegistry 提供类型匹配；specifications 向技术适配暴露订阅描述。
边界约束：只维护订阅快照与匹配规则，不含投递、重试或网络传输实现。
"""

import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Annotated

from deermind.abstractions.delivery import Acceptance, EventNotice, SubscriptionSpec
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncConnection

Name = Annotated[str, Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")]


@dataclass(frozen=True)
class Subscription:
    """仅装配层注册，M1业务从新事件开始；历史补送由单独维护授权决定。"""

    subscriber_id: str
    revision: str
    event_types: frozenset[str]
    scope_kinds: frozenset[str]
    accept: Callable[[AsyncConnection, EventNotice], Awaitable[Acceptance]]


class SubscriptionRegistry:
    """固定订阅快照；禁止投递留痕订阅自己，避免无限事件循环。"""

    def __init__(self, subscriptions: Sequence[Subscription]) -> None:
        self.items = tuple(subscriptions)
        names: set[str] = set()
        # 逐条校验订阅：去重、必备集合、禁订阅交接事件自身、回调可调用、命名合法。
        for item in self.items:
            # 重复订阅者、空版本/类型/范围、订阅 DeliveryStateChanged 自身或回调不可调用均判无效。
            if (
                item.subscriber_id in names
                or not item.revision
                or not item.event_types
                or not item.scope_kinds
                or "DeliveryStateChanged" in item.event_types
                or not callable(item.accept)
                or any(
                    re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name) is None
                    for name in (item.subscriber_id, *item.event_types, *item.scope_kinds)
                )
            ):
                raise ValueError("Invalid or duplicate subscription")
            names.add(item.subscriber_id)

    def matching(self, event_type: str, scope_kind: str) -> list[Subscription]:
        """按事件类型与范围种类筛选命中的订阅者。"""
        # 同时匹配事件类型与范围种类才纳入本次通知。
        return [
            item
            for item in self.items
            if event_type in item.event_types and scope_kind in item.scope_kinds
        ]


def specifications(registry: SubscriptionRegistry) -> tuple[SubscriptionSpec, ...]:
    """技术适配只接收订阅描述，不获得事务回调。"""
    return tuple(
        SubscriptionSpec(s.subscriber_id, s.revision, s.event_types, s.scope_kinds)
        for s in registry.items
    )
