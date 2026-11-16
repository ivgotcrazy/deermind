"""AI所有者的完整事实正文；不保存凭据，不把技术候选当作正式业务结果。"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from deermind.foundation.system.events.contracts import FactModel, NonEmpty, Ref
from pydantic import Field, JsonValue, model_validator

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


class ModelRequestFact(FactModel):
    """一次真实外发的预约和已知结果；响应丢失时保留预约，不填零用量。"""

    call_id: UUID
    attempt_id: UUID
    request_ordinal: Ordinal
    transport_attempt: Ordinal
    model: NonEmpty
    request_ref: Ref
    reserved_input_tokens: Count
    reserved_output_tokens: Count
    actual_input_tokens: Count | None
    actual_output_tokens: Count | None
    usage_state: Literal["reserved", "known", "unknown"]
    provider_request_id: str | None
    outcome: Literal["pending", "success", "failed", "unknown"]
    started_at: datetime
    finished_at: datetime | None
    response_ref: Ref | None

    @model_validator(mode="after")
    def consistent_usage(self) -> "ModelRequestFact":
        """完整用量才标known；未知和预约不能冒充实际计费。"""
        if self.usage_state == "known":
            if self.actual_input_tokens is None or self.actual_output_tokens is None:
                raise ValueError("Known usage requires both token counts")
        elif self.actual_input_tokens is not None or self.actual_output_tokens is not None:
            raise ValueError("Unknown usage cannot contain actual token counts")
        if (self.outcome == "pending") != (self.finished_at is None):
            raise ValueError("Only pending requests may have no finish time")
        return self


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
