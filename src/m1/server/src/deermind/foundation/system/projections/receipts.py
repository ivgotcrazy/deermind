"""投影处理的通用防重记录；不执行转换，不读取或写入业务投影表。"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@asynccontextmanager
async def application(
    connection: AsyncConnection, projector_id: str, generation: int, event_id: UUID
) -> AsyncGenerator[bool]:
    """业务持有同一事务：成功才登记完成，重复返回False；异常由外层整体回滚。"""
    if not connection.in_transaction() or not projector_id or generation < 1:
        raise ValueError("Projection receipt requires an active transaction and stable identity")
    parameters = {"projector": projector_id, "generation": generation, "event": event_id}
    await connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"projection:{projector_id}:{generation}:{event_id}"},
    )
    exists = await connection.scalar(
        text(
            "SELECT 1 FROM runtime.projection_receipts WHERE projector_id=:projector "
            "AND generation=:generation AND event_id=:event"
        ),
        parameters,
    )
    if exists:
        yield False
        return
    yield True
    await connection.execute(
        text(
            "INSERT INTO runtime.projection_receipts "
            "(projector_id,generation,event_id,applied_at) "
            "VALUES (:projector,:generation,:event,clock_timestamp())"
        ),
        parameters,
    )
