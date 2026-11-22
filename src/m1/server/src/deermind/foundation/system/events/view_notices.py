"""用已提交事件确定待刷新的资源与视图。"""

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
    if event is None:
        return None
    views = routes.get((event.event_type, event.scope_kind))
    if not views:
        return None
    return ViewChange(event.scope_kind, str(event.scope_id), views)
