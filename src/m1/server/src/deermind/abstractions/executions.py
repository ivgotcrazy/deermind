"""执行身份、命令和边界数据；不包含注册器或数据库事务。"""

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from deermind.abstractions.events import FactModel, Ref

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
    """固定启动、取消或唤醒命令；Workflow和队列不由外部请求选择。"""

    model_config = ConfigDict(extra="forbid")
    run: RunInput
    workflow_id: str
    workflow_type: str
    task_queue: str
    wait_id: UUID | None = None


class Limits(BaseModel):
    """执行接线的有限上限，由装配层按已确认值显式提供。"""

    model_config = ConfigDict(extra="forbid", frozen=True)
    request_seconds: int = Field(gt=0)
    attempts: int = Field(gt=0)
    budget_seconds: int = Field(gt=0)
    lease_seconds: int = Field(gt=0)
    reconcile_seconds: int = Field(gt=0)
    finalize_seconds: int = Field(gt=0)


class ExecutionNotFound(LookupError):
    """技术执行不存在；调用方结合持久交接状态决定如何处理。"""


class ExecutionTransport(Protocol):
    @property
    def limits(self) -> Limits: ...
    async def start(self, command: Dispatch) -> str: ...
    async def signal(self, command: Dispatch) -> None: ...
    async def cancel(self, command: Dispatch) -> None: ...
    async def running(self, command: Dispatch) -> bool: ...


class LifecycleService(Protocol):
    async def started(self, run: RunInput) -> None: ...
    async def completed(self, run: RunInput, result: Ref) -> None: ...
    async def failed(self, run: RunInput, error_code: str) -> None: ...
