"""后台工作的固定身份及步骤合同；输入、实现和授权不能由恢复请求替换。"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Authorization, Execution, State
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class Entry:
    """模块提供短事务校验与收尾；注册对象不从请求或模型输出反序列化。

    lock先取得所有者业务锁，再由底座锁执行行，保持全局锁序。
    check负责当前资格、业务位置及剩余额度；finalize负责业务收尾。
    三者只能使用传入事务，不能调用模型或外部服务。
    """

    owner: str
    name: str
    kind: Literal["ai_operation", "handler"]
    implementation_ref: Ref
    workflow_type: str
    task_queue: str
    lock: Callable[[AsyncConnection, str, UUID], Awaitable[None]]
    check: Callable[[AsyncConnection, Execution, Authorization, str], Awaitable[None]]
    finalize: Callable[[AsyncConnection, Execution, State, Ref | None], Awaitable[None]]


class Registry:
    """只接受程序提供的入口；旧合同不可静默换成同名新实现。"""

    def __init__(self, entries: Sequence[Entry]) -> None:
        self.entries: dict[str, Entry] = {}
        for entry in entries:
            if entry.name in self.entries or not entry.name.startswith(entry.owner + "."):
                raise ValueError("Duplicate entry or invalid owner")
            if not entry.workflow_type or not entry.task_queue:
                raise ValueError("Workflow and queue registration are required")
            self.entries[entry.name] = entry

    def resolve(self, execution: Execution) -> Entry:
        entry = self.entries[execution.entry_ref]
        if (
            entry.owner != execution.owner
            or entry.kind != execution.kind
            or entry.implementation_ref != execution.implementation_ref
        ):
            raise ValueError("Execution implementation is unavailable or incompatible")
        return entry


@dataclass(frozen=True)
class Caller:
    """由已认证入口或维护命令构造；不是浏览器可自报的授权。"""

    actor: Ref
    owner: str
    scopes: frozenset[tuple[str, UUID]]
    actions: frozenset[str]

    def require(self, execution: Execution, action: str) -> None:
        if (
            execution.owner != self.owner
            or (execution.scope_kind, execution.scope_id) not in self.scopes
            or action not in self.actions
        ):
            raise PermissionError("Execution access denied")
