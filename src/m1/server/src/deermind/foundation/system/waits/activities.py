"""等待Activity使用的底座事务服务；不依赖Temporal。"""

import asyncio

from deermind.abstractions.waits import Handling, Wait, WaitCall
from deermind.foundation.system.waits.service import Waits
from sqlalchemy.ext.asyncio import AsyncEngine


class WaitActions:
    def __init__(self, engine: AsyncEngine, waits: Waits, *, timeout_seconds: int) -> None:
        self.engine, self.waits, self.timeout_seconds = engine, waits, timeout_seconds

    async def probe(self, call: WaitCall) -> Wait:
        async with asyncio.timeout(self.timeout_seconds), self.engine.begin() as connection:
            return await self.waits.probe(connection, call.run, call.wait_id)

    async def handle(self, call: WaitCall) -> Handling:
        async with asyncio.timeout(self.timeout_seconds), self.engine.begin() as connection:
            return await self.waits.handle(connection, call.run, call.wait_id)
