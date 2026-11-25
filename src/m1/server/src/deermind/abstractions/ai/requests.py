"""模型请求预约及结算数据；不包含账本实现。

分层定位：abstractions（AI 跨层合同）
对外契约：ModelRequestFact 一次真实外发的预约与结果记录。
边界约束：只定义用量与状态结构，账本记账与结算由 foundation 承接。
"""

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
        # known 状态必须双令牌齐全，缺一不可。
        if self.usage_state == "known":
            if self.actual_input_tokens is None or self.actual_output_tokens is None:
                raise ValueError("Known usage requires both token counts")
        # reserved/unknown 状态不得携带实际令牌，避免冒充已结算用量。
        elif self.actual_input_tokens is not None or self.actual_output_tokens is not None:
            raise ValueError("Unknown usage cannot contain actual token counts")
        # 仅 pending 可无结束时间；其余终态必须带 finished_at。
        if (self.outcome == "pending") != (self.finished_at is None):
            raise ValueError("Only pending requests may have no finish time")
        return self
