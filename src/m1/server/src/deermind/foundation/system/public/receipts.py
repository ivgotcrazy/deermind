"""统一收据的只读合同；业务结果由所有者提供，不在底座解释。

分层定位：foundation（公共运行底座 / 公开收据合同）
对外契约：ReceiptQuery 描述一次收据查询条件；ReceiptView 描述返回的收据状态与业务结果。
边界约束：底座只承载收据身份与状态，业务结果语义由对应业务所有者解释。
"""

from typing import Literal
from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.foundation.system.public.errors import ErrorDetail
from pydantic import BaseModel, ConfigDict, Field


class ReceiptQuery(BaseModel):
    """收据查询条件：动作、资源类型/编号与受理请求号。"""

    model_config = ConfigDict(extra="forbid")
    action: str = Field(min_length=1, max_length=128)
    resource_kind: str = Field(min_length=1, max_length=64)
    resource_id: UUID
    request_id: str = Field(min_length=1, max_length=128)


class ReceiptView[Result: BaseModel](BaseModel):
    """收据只读视图：收据状态、引用、业务状态、结果、错误与执行信息。"""

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
