"""等待策略由业务模块登记；E01不预设教学条件或制造业务等待。"""

from deermind.bootstrap.executions import registry
from deermind.foundation.system.waits.contracts import Policies
from deermind.foundation.system.waits.service import Waits


def policies() -> Policies:
    return Policies([])


def waits() -> Waits:
    return Waits(registry(), policies(), maximum_seconds=300)
