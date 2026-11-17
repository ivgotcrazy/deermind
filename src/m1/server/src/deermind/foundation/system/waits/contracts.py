"""等待、结果及程序登记；消息只唤醒，不能携带回调或扩大读取范围。"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Execution
from deermind.abstractions.waits import Condition, Match, Wait
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class Policy:
    """所有者登记只读probe和同事务接续；两者都不调用AI或远程服务。"""

    ref: Ref
    event_types: frozenset[str]
    scope_kinds: frozenset[str]
    on_match: str
    on_timeout: str
    probe: Callable[[AsyncConnection, Execution, Condition], Awaitable[Match | None]]
    handle: Callable[[AsyncConnection, Execution, Wait], Awaitable[Ref]]


class Policies:
    def __init__(self, items: Sequence[Policy]) -> None:
        self.items = tuple(items)
        if len({p.ref.model_dump_json() for p in items}) != len(items):
            raise ValueError("Duplicate wait policy")
        for item in items:
            if not item.event_types or not item.scope_kinds or not item.ref.revision:
                raise ValueError("Wait policy needs fixed revision, types and scopes")
            if any(
                not name.startswith(item.ref.owner + ".")
                for name in (item.on_match, item.on_timeout)
            ):
                raise ValueError("Wait handlers must belong to their owner")

    def resolve(self, wait: Wait, execution: Execution) -> Policy:
        policy = next((p for p in self.items if p.ref == wait.probe_ref), None)
        if (
            policy is None
            or policy.ref.owner != execution.owner
            or wait.owner_ref.owner != execution.owner
            or wait.execution_id != execution.execution_id
            or wait.on_match != policy.on_match
            or wait.on_timeout != policy.on_timeout
            or not set(wait.condition.event_types) <= policy.event_types
            or wait.condition.scope_kind not in policy.scope_kinds
            or wait.condition.scope_id != execution.scope_id
            or wait.condition.scope_kind != execution.scope_kind
        ):
            raise PermissionError("Wait policy or resource scope is not authorized")
        return policy
