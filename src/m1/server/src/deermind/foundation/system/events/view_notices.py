"""用已提交事件确定待刷新的资源与视图。

分层定位：foundation（公共运行底座 / 事件视图）
对外契约：resolve_view_change 按登记路由把正式事件映射为可授权的刷新范围。
边界约束：查询只取事件类型与范围，不读取事件正文；进一步授权由连接层完成。
"""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True)
class ViewChange:
    """可交给连接层进一步授权的刷新范围。"""

    kind: str
    resource_id: str
    views: frozenset[str]


async def resolve_view_change(
    engine: AsyncEngine,
    event_id: UUID,
    routes: Mapping[tuple[str, str], frozenset[str]],
) -> ViewChange | None:
    """按所有者登记的类型与范围匹配正式事件，查询不读取正文。"""
    # 无登记路由，本部署不处理该类事件的视图刷新。
    if not routes:
        return None
    async with engine.connect() as connection:
        event = (
            await connection.execute(
                text(
                    "SELECT event_type, scope_kind, scope_id FROM runtime.events "
                    "WHERE event_id=:event_id"
                ),
                {"event_id": event_id},
            )
        ).one_or_none()
    # 事件不存在，无可刷新范围。
    if event is None:
        return None
    views = routes.get((event.event_type, event.scope_kind))
    # 该类型与范围未登记刷新视图，忽略。
    if not views:
        return None
    return ViewChange(event.scope_kind, str(event.scope_id), views)
