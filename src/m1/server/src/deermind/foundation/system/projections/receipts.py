"""投影处理的通用防重记录；不执行转换，不读取或写入业务投影表。

分层定位：foundation（公共运行底座 / 投影防重）
对外契约：application 在同一事务内为单条事件登记投影完成记录，重复应用返回 False。
边界约束：防重只按投影器、生成号、事件编号记账；投影转换与业务投影表由投影器自行负责。
"""

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
    # 必须处于调用方开启的事务内，且投影器身份与生成号有效，否则防重不可靠。
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
    # 该事件已被本投影器应用过，重复应用返回 False，不再写防重记录。
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
