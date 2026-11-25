"""AI 所有者的完整事实正文；不保存凭据，不把技术候选当作正式业务结果。

分层定位：foundation（AI 底座）
对外契约：配置、调用、尝试、工具动作、候选等事实记录模型，供事件登记与投影使用。
边界约束：只定义事实结构，不含账本记账、模型调用与候选接受逻辑。
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from deermind.abstractions.events import FactModel, NonEmpty, Ref
from pydantic import Field, JsonValue

Count = Annotated[int, Field(ge=0)]
Ordinal = Annotated[int, Field(ge=1)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ConfigurationFact(FactModel):
    """一次工作的固定配置；config由配置合同再次校验，不能放入认证头。"""

    execution_id: UUID
    config_revision: NonEmpty
    config_hash: Digest
    config: dict[str, JsonValue]
    created_at: datetime


class CallFact(FactModel):
    """稳定调用身份和当前技术状态；输入相同才允许复用候选。"""

    call_id: UUID
    execution_id: UUID
    step_key: NonEmpty
    call_key: NonEmpty
    input_hash: Digest
    purpose: NonEmpty
    schema_ref: Ref
    input_ref: Ref
    state: Literal["pending", "running", "completed", "failed", "cancelled"]
    candidate_ref: UUID | None
    created_at: datetime


class CallAttemptFact(FactModel):
    """恢复产生新尝试；单次HTTP重试不产生新的AI调用尝试。"""

    call_id: UUID
    attempt_id: UUID
    execution_attempt_id: UUID
    attempt_no: Ordinal
    started_at: datetime
    finished_at: datetime | None
    outcome: Literal["running", "completed", "failed", "cancelled", "unknown"]
    error: dict[str, JsonValue] | None
    valid_candidate: bool


class ToolActionFact(FactModel):
    """工具授权及已知结果；业务副作用仍由工具所有者另行留痕。"""

    tool_action_key: NonEmpty
    attempt_id: UUID
    call_id: UUID
    tool_name: NonEmpty
    parameters_ref: Ref
    result_ref: Ref | None
    authorization_result: Literal["allowed", "denied"]
    work_key: str | None
    owner_receipt_ref: Ref | None
    outcome: Literal["pending", "completed", "failed", "denied"]
    started_at: datetime
    finished_at: datetime | None


class CandidateFact(FactModel):
    """按用途Schema通过结构校验的候选，业务接受与提交由调用方决定。"""

    candidate_id: UUID
    call_id: UUID
    schema_ref: Ref
    content: dict[str, JsonValue]
    material_refs: list[Ref]
    tool_refs: list[Ref]
    content_hash: Digest
    created_at: datetime
