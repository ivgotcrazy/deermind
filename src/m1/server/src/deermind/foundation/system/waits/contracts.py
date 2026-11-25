"""等待、结果及程序登记；消息只唤醒，不能携带回调或扩大读取范围。

分层定位：foundation（公共运行底座 / 等待策略合同）
对外契约：Policy 登记单个等待条件的探测与接续程序；Policies 按等待身份解析并核对归属与范围。
边界约束：probe/handle 为所有者登记的只读探测与同事务接续；两者均不调用 AI 或远程服务。
"""

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
    """等待策略登记集合：校验策略唯一性、固定修订号、事件类型与归属。"""

    def __init__(self, items: Sequence[Policy]) -> None:
        self.items = tuple(items)
        # 策略引用身份重复会导致等待定位歧义。
        if len({p.ref.model_dump_json() for p in items}) != len(items):
            raise ValueError("Duplicate wait policy")
        for item in items:
            # 事件类型、范围种类与固定修订号缺一不可。
            if not item.event_types or not item.scope_kinds or not item.ref.revision:
                raise ValueError("Wait policy needs fixed revision, types and scopes")
            # 匹配/超时处理程序必须挂在本所有者命名空间下，不能跨所有者接线。
            if any(
                not name.startswith(item.ref.owner + ".")
                for name in (item.on_match, item.on_timeout)
            ):
                raise ValueError("Wait handlers must belong to their owner")

    def resolve(self, wait: Wait, execution: Execution) -> Policy:
        """按等待身份解析策略，并核对所有者、执行、条件类型与范围一致。"""
        policy = next((p for p in self.items if p.ref == wait.probe_ref), None)
        # 策略未登记，或所有者/执行/处理程序/条件类型与范围任一不符，判未授权。
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
