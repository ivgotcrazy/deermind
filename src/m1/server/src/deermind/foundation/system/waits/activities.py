"""等待 Activity 使用的底座事务服务；不依赖 Temporal。

分层定位：foundation（公共运行底座 / 等待适配）
对外契约：WaitActions 把等待探测/接续动作包装为带超时的独立事务服务。
边界约束：本层只转发到 Waits 底座服务，不直接访问等待表，也不引入 Temporal 适配细节。
"""

import asyncio

from deermind.abstractions.waits import Handling, Wait, WaitCall
from deermind.foundation.system.waits.service import Waits
from sqlalchemy.ext.asyncio import AsyncEngine


class WaitActions:
    """等待 Activity 的事务适配：在独立事务与超时内调用等待底座。"""

    def __init__(self, engine: AsyncEngine, waits: Waits, *, timeout_seconds: int) -> None:
        self.engine, self.waits, self.timeout_seconds = engine, waits, timeout_seconds

    async def probe(self, call: WaitCall) -> Wait:
        """在带超时事务内探测等待条件是否命中。"""
        async with asyncio.timeout(self.timeout_seconds), self.engine.begin() as connection:
            return await self.waits.probe(connection, call.run, call.wait_id)

    async def handle(self, call: WaitCall) -> Handling:
        """在带超时事务内接续已命中的等待。"""
        async with asyncio.timeout(self.timeout_seconds), self.engine.begin() as connection:
            return await self.waits.handle(connection, call.run, call.wait_id)
