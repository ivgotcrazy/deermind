"""统一收据的只读合同；业务结果由所有者提供，不在底座解释。"""

from typing import Literal
from uuid import UUID

from deermind.foundation.system.events.contracts import Ref
from deermind.foundation.system.public.errors import ErrorDetail
from pydantic import BaseModel, ConfigDict, Field


class ReceiptQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(min_length=1, max_length=128)
    resource_kind: str = Field(min_length=1, max_length=64)
    resource_id: UUID
    request_id: str = Field(min_length=1, max_length=128)


class ReceiptView[Result: BaseModel](BaseModel):
    model_config = ConfigDict(extra="forbid")
    receipt_state: Literal["not_found", "accepted", "completed", "rejected"]
    receipt_ref: UUID | None = None
    business_state: str | None = None
    result: Result | None = None
    error: ErrorDetail | None = None
    execution_ref: UUID | None = None
    execution_state: str | None = None
    result_refs: list[Ref] = Field(default_factory=list[Ref])
    allowed_actions: list[str] = Field(default_factory=list[str])
