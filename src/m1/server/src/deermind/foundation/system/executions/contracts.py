"""后台工作的固定身份及步骤合同；输入、实现和授权不能由恢复请求替换。"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from deermind.foundation.system.events.contracts import FactModel, Ref
from pydantic import BaseModel, ConfigDict, Field, JsonValue
from sqlalchemy.ext.asyncio import AsyncConnection

State = Literal["ready", "running", "waiting", "completed", "failed", "cancelled"]


class Execution(FactModel):
    execution_id: UUID
    kind: Literal["ai_operation", "handler"]
    owner: str
    entry_ref: str
    scope_kind: str
    implementation_ref: Ref
    ai_config_ref: UUID | None
    scope_id: UUID
    acceptance_key: str
    input_ref: Ref
    active_attempt_id: UUID | None
    state: State
    result_ref: Ref | None
    failure_ref: Ref | None
    created_at: datetime
    updated_at: datetime


class Attempt(FactModel):
    attempt_id: UUID
    execution_id: UUID
    attempt_no: int
    retry_request_id: str | None
    previous_attempt_id: UUID | None
    workflow_id: str
    temporal_run_id: str | None
    accepted_at: datetime
    deadline_at: datetime
    state: State
    failure_ref: Ref | None
    finished_at: datetime | None


class Authorization(FactModel):
    execution_id: UUID
    initiator_ref: Ref
    owner: str
    entry: str
    resource_scope: dict[str, JsonValue]
    allowed_actions: list[str]
    basis_refs: list[Ref]
    created_at: datetime


class StepResult(FactModel):
    execution_id: UUID
    step_name: str
    occurrence_key: str
    input_hash: str
    output_ref: Ref
    owner_receipt_ref: Ref | None
    completed_by_attempt: UUID
    created_at: datetime


class RunInput(FactModel):
    """Workflow只带固定引用，原始正文由所有者按权限读取。"""

    execution_id: UUID
    attempt_id: UUID
    input_ref: Ref
    implementation_ref: Ref
    ai_config_ref: UUID | None
    deadline_at: datetime


class Dispatch(BaseModel):
    """固定启动或取消命令；登记的Workflow和队列不由外部请求选择。"""

    model_config = ConfigDict(extra="forbid")
    run: RunInput
    workflow_id: str
    workflow_type: str
    task_queue: str


class Limits(BaseModel):
    """执行接线的有限上限，由装配层按已确认值显式提供。"""

    model_config = ConfigDict(extra="forbid", frozen=True)
    request_seconds: int = Field(gt=0)
    attempts: int = Field(gt=0)
    budget_seconds: int = Field(gt=0)
    lease_seconds: int = Field(gt=0)
    reconcile_seconds: int = Field(gt=0)
    finalize_seconds: int = Field(gt=0)


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
