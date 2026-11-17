"""执行生命周期短事务；由SDK Activity通过独立接口调用。"""

import asyncio

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Limits, RunInput
from deermind.foundation.system.executions import commands
from deermind.foundation.system.executions.contracts import Registry
from sqlalchemy.ext.asyncio import AsyncEngine


class Lifecycle:
    def __init__(self, engine: AsyncEngine, registry: Registry, limits: Limits) -> None:
        self.engine, self.registry, self.limits = engine, registry, limits

    async def started(self, run: RunInput) -> None:
        async with self.engine.begin() as connection:
            await commands.start(connection, self.registry, run)

    async def completed(self, run: RunInput, result: Ref) -> None:
        async with asyncio.timeout(self.limits.finalize_seconds), self.engine.begin() as connection:
            await commands.complete(connection, self.registry, run, result)

    async def failed(self, run: RunInput, error_code: str) -> None:
        failure = Ref(
            owner="runtime", type="execution_failure", id=str(run.attempt_id), path=error_code
        )
        async with asyncio.timeout(self.limits.finalize_seconds), self.engine.begin() as connection:
            await commands.fail(connection, self.registry, run, failure)
