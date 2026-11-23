"""装配业务等待的固定条件。"""

from deermind.bootstrap.executions import registry
from deermind.foundation.system.executions.contracts import Registry
from deermind.foundation.system.waits.contracts import Policies
from deermind.foundation.system.waits.service import Waits
from deermind.spaces.domain.supply import TaskSupply
from deermind.spaces.interaction.supply_wait import policy


def policies() -> Policies:
    return Policies([policy(TaskSupply.find_batch_result)])


def waits(entries: Registry | None = None) -> Waits:
    return Waits(entries or registry(), policies(), maximum_seconds=300)
