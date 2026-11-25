"""执行生命周期短事务；由 SDK Activity 通过独立接口调用。

分层定位：foundation（公共运行底座 / 执行生命周期）
对外契约：Lifecycle 实现 LifecycleService，承接执行开始、完成、失败的状态回写。
边界约束：每个动作为独立短事务；收尾时限受 finalize_seconds 限制；不含业务收尾逻辑。
"""

import asyncio

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Limits, RunInput
from deermind.foundation.system.executions import commands
from deermind.foundation.system.executions.contracts import Registry
from sqlalchemy.ext.asyncio import AsyncEngine


class Lifecycle:
    """执行生命周期状态回写服务：持有引擎、入口登记与时限上限。"""

    def __init__(self, engine: AsyncEngine, registry: Registry, limits: Limits) -> None:
        self.engine, self.registry, self.limits = engine, registry, limits

    async def started(self, run: RunInput) -> None:
        """登记执行开始。"""
        async with self.engine.begin() as connection:
            await commands.start(connection, self.registry, run)

    async def completed(self, run: RunInput, result: Ref) -> None:
        """提交执行结果并完成收尾。"""
        async with asyncio.timeout(self.limits.finalize_seconds), self.engine.begin() as connection:
            await commands.complete(connection, self.registry, run, result)

    async def failed(self, run: RunInput, error_code: str) -> None:
        """登记执行失败与失败引用。"""
        failure = Ref(
            owner="runtime", type="execution_failure", id=str(run.attempt_id), path=error_code
        )
        async with asyncio.timeout(self.limits.finalize_seconds), self.engine.begin() as connection:
            await commands.fail(connection, self.registry, run, failure)
