"""领域管理的公开模型和应用端口。"""

from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator

from deermind.abstractions.events import FactModel, Ref
from deermind.foundation.system.public.errors import Issue
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.public.authentication import SessionView
from deermind.spaces.domain.rich_content import RichContent, invalid

__all__ = [
    "SAVE_ACTION",
    "CreateDomainRequest",
    "CreateDomainResponse",
    "CreateDomainResult",
    "DomainContentRef",
    "DomainDefinition",
    "DomainDetail",
    "DomainList",
    "DomainRef",
    "DomainRow",
    "DomainService",
    "DomainView",
    "NonBlank",
    "RichContent",
]

SAVE_ACTION = "domain.save_definition"

type NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
type RequestId = Annotated[str, Field(min_length=1, max_length=128)]
type Version = Annotated[int, Field(ge=1)]


class DomainRef(FactModel):
    kind: Literal["domain"] = "domain"
    object_id: UUID
    version: Version


class DomainDefinition(FactModel):
    """拥有名称及可选的说明和覆盖范围。"""

    name: NonBlank
    coverage: RichContent | None = None
    description: RichContent | None = None

    @field_validator("coverage", "description")
    @classmethod
    def validate_content(cls, content: RichContent | None) -> RichContent | None:
        if content is None:
            return None
        if content.role != "definition":
            invalid("DomainDefinition", ("role",), "领域说明和覆盖范围只能使用定义正文。")
        if content.source_refs:
            invalid("DomainDefinition", ("source_refs",), "此入口暂未提供外部来源授权。")
        return content


class DomainContentRef(FactModel):
    owner: Literal["domain"] = "domain"
    object_ref: DomainRef
    path: Literal[""] = ""


class CreateDomainRequest(FactModel):
    request_id: RequestId
    object_kind: Literal["domain"]
    action: Literal["create"]
    definition: DomainDefinition
    change_note: NonBlank


class CreateDomainResult(FactModel):
    object_ref: DomainRef
    content_ref: DomainContentRef
    gaps: list[Issue] = Field(default_factory=list[Issue])


class CreateDomainResponse(FactModel):
    request_ref: UUID
    result: CreateDomainResult


class DomainRow(FactModel):
    object_ref: DomainRef
    name: str
    description: None = None
    is_deleted: bool
    source_event_id: UUID


class DomainList(FactModel):
    items: list[DomainRow]


class DomainView(FactModel):
    object_ref: DomainRef
    content: DomainDefinition
    content_ref: DomainContentRef
    is_identity_deleted: bool
    source_refs: list[Ref] = Field(default_factory=list[Ref])
    source_event_id: UUID
    gaps: list[Issue] = Field(default_factory=list[Issue])


class DomainDetail(FactModel):
    object: DomainView


class DomainService(Protocol):
    """当前会话由入口核验，应用端口执行领域权限和范围判断。"""

    async def list_domains(self, session: SessionView) -> DomainList: ...

    async def read_domain(
        self,
        session: SessionView,
        domain_id: UUID,
        object_id: UUID,
        version: int | None = None,
    ) -> DomainDetail: ...

    async def create_domain(
        self, session: SessionView, body: CreateDomainRequest
    ) -> CreateDomainResponse: ...

    async def read_receipt(
        self, principal_id: UUID, session_id: UUID, query: ReceiptQuery
    ) -> ReceiptView[CreateDomainResult]: ...
