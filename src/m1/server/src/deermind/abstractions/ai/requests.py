"""模型请求预约及结算数据；不包含账本实现。"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from deermind.abstractions.events import FactModel, NonEmpty, Ref

Count = Annotated[int, Field(ge=0)]
Ordinal = Annotated[int, Field(ge=1)]


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
