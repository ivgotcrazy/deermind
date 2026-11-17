"""首次使用确认的网页合同；管理员操作由受控命令承载。"""

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.public.authentication import AuthModel, SessionView, UsageGap
from pydantic import Field


class UsageView(AuthModel):
    student_id: UUID
    revision: int
    notice_ref: Ref
    notice_text: str
    source_ref: Ref
    allowed: bool
    gaps: list[UsageGap]
    can_confirm: bool


class ConfirmationInput(AuthModel):
    student_id: UUID
    kind: Literal["guardian_consent", "student_assent"]
    notice_ref: Ref
    decision: Literal["accepted", "declined", "pending"]
    occurred_at: datetime | None = None
    source_ref: Ref


class ConfirmUsageRequest(AuthModel):
    request_id: UUID
    expected_revision: int = Field(ge=1)
    confirmation: ConfirmationInput


class ConfirmationResult(AuthModel):
    confirmation_ref: Ref
    conditions_revision: int
    allowed: bool
    gaps: list[UsageGap]


class ConfirmUsageResponse(AuthModel):
    request_ref: UUID
    result: ConfirmationResult


class UsageService(Protocol):
    async def read_receipt(
        self, principal: UUID, session: UUID, query: ReceiptQuery
    ) -> ReceiptView[ConfirmationResult]: ...

    async def view(self, session: SessionView) -> UsageView: ...
    async def confirm(
        self, session: SessionView, body: ConfirmUsageRequest
    ) -> ConfirmUsageResponse: ...
