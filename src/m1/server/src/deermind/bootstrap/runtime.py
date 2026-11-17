"""将底座事务服务注入SDK外壳；不执行工作或产生业务事实。"""

from deermind.abstractions.executions import Limits
from deermind.foundation.system.executions.contracts import Registry
from deermind.foundation.system.executions.lifecycle import Lifecycle as LifecycleService
from deermind.foundation.system.waits.activities import WaitActions
from deermind.foundation.system.waits.service import Waits
from deermind.infrastructure.temporal.executions import Lifecycle
from deermind.infrastructure.temporal.waits import Activities
from sqlalchemy.ext.asyncio import AsyncEngine


def lifecycle(engine: AsyncEngine, entries: Registry, limits: Limits) -> Lifecycle:
    return Lifecycle(LifecycleService(engine, entries, limits))


def wait_activities(engine: AsyncEngine, waits: Waits, *, timeout_seconds: int) -> Activities:
    return Activities(WaitActions(engine, waits, timeout_seconds=timeout_seconds))
