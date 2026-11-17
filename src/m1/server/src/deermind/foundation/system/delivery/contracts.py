"""进程内订阅合同及严格通知格式；通知不携带正文或读取授权。"""

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
        for item in self.items:
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
