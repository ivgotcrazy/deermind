"""领域管理的公开模型和应用端口。"""

from typing import Annotated, Literal, Protocol, cast
from uuid import UUID

from pydantic import Discriminator, Field, StringConstraints, Tag, field_validator

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
type Version = Annotated[int, Field(ge=1, le=2**63 - 1)]
type JsonUuid = Annotated[UUID, Field(strict=False)]
type MemberKind = Literal["kc", "task"]


class DomainRef(FactModel):
    kind: Literal["domain"] = "domain"
    object_id: UUID
    version: Version


class KnowledgeRef(FactModel):
    kind: Literal["kc"]
    object_id: JsonUuid
    version: Version


class TaskRef(FactModel):
    kind: Literal["task"]
    object_id: JsonUuid
    version: Version


type MemberRef = KnowledgeRef | TaskRef
type ObjectRef = DomainRef | MemberRef


def definition_content(content: RichContent | None, title: str) -> RichContent | None:
    if content is None:
        return None
    if content.role != "definition":
        invalid(title, ("role",), "此字段只能使用定义正文。")
    if content.source_refs:
        invalid(title, ("source_refs",), "此入口暂未提供外部来源授权。")
    return content


class DomainDefinition(FactModel):
    """拥有名称及可选的说明和覆盖范围。"""

    name: NonBlank
    coverage: RichContent | None = None
    description: RichContent | None = None

    @field_validator("coverage", "description")
    @classmethod
    def validate_content(cls, content: RichContent | None) -> RichContent | None:
        return definition_content(content, cls.__name__)


class KnowledgeComponent(FactModel):
    """含义与适用条件为必填，例子可单独补充。"""

    name: NonBlank
    definition: RichContent
    applicability: RichContent
    examples: RichContent | None = None
    non_examples: RichContent | None = None

    @field_validator("definition", "applicability", "examples", "non_examples")
    @classmethod
    def validate_content(cls, content: RichContent | None) -> RichContent | None:
        if content is not None and not content.blocks:
            invalid(cls.__name__, ("blocks",), "请提供正文。")
        return definition_content(content, cls.__name__)


class TaskParameter(FactModel):
    name: NonBlank
    meaning: NonBlank
    type: NonBlank
    constraints: NonBlank


class TaskDefinition(FactModel):
    """可保存未填齐的定义；就绪要求与个人评价独立。"""

    name: NonBlank
    responsibility: RichContent | None = None
    expected_output: RichContent | None = None
    completion_conditions: RichContent | None = None
    applicability: RichContent | None = None
    boundaries: RichContent | None = None
    parameters: list[TaskParameter] = Field(default_factory=list[TaskParameter])

    @field_validator(
        "responsibility", "expected_output", "completion_conditions", "applicability", "boundaries"
    )
    @classmethod
    def validate_content(cls, content: RichContent | None) -> RichContent | None:
        if content is not None and not any(
            block.type != "paragraph"
            or any(span.type != "text" or span.text.strip() for span in block.payload.spans)
            for block in content.blocks
        ):
            invalid(cls.__name__, ("blocks",), "请提供正文，未填项请留空。")
        return definition_content(content, cls.__name__)

    @field_validator("parameters")
    @classmethod
    def unique_parameters(cls, parameters: list[TaskParameter]) -> list[TaskParameter]:
        seen: set[str] = set()
        for index, parameter in enumerate(parameters):
            if parameter.name in seen:
                invalid(cls.__name__, (index, "name"), "参数名称重复。")
            seen.add(parameter.name)
        return parameters


def task_gaps(content: TaskDefinition) -> list[Issue]:
    fields = (
        ("responsibility", content.responsibility, "认知责任"),
        ("expected_output", content.expected_output, "预期表现"),
        ("completion_conditions", content.completion_conditions, "完成条件"),
        ("applicability", content.applicability, "适用条件"),
        ("boundaries", content.boundaries, "适用边界"),
    )
    return [
        Issue(code="missing_content", path=f"/{field}", message=f"请补充{label}。")
        for field, value, label in fields
        if value is None
    ] + [Issue(code="missing_methods", path="/method_refs", message="尚未关联方法。")]


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


class _KnowledgeRequest(FactModel):
    request_id: RequestId
    object_kind: Literal["kc"]
    change_note: NonBlank


class CreateKnowledgeRequest(_KnowledgeRequest):
    action: Literal["create"]
    domain_id: JsonUuid
    definition: KnowledgeComponent


class UpdateKnowledgeRequest(_KnowledgeRequest):
    action: Literal["update"]
    object_ref: KnowledgeRef
    expected_version: Version
    definition: KnowledgeComponent


class DeleteKnowledgeRequest(_KnowledgeRequest):
    action: Literal["soft_delete"]
    object_ref: KnowledgeRef
    expected_version: Version


class _TaskRequest(FactModel):
    request_id: RequestId
    object_kind: Literal["task"]
    change_note: NonBlank


class CreateTaskRequest(_TaskRequest):
    action: Literal["create"]
    domain_id: JsonUuid
    definition: TaskDefinition


class UpdateTaskRequest(_TaskRequest):
    action: Literal["update"]
    object_ref: TaskRef
    expected_version: Version
    definition: TaskDefinition


class DeleteTaskRequest(_TaskRequest):
    action: Literal["soft_delete"]
    object_ref: TaskRef
    expected_version: Version


def save_variant(value: object) -> str | None:
    """同时以对象种类和动作定位唯一请求模型。"""
    if isinstance(value, dict):
        data = cast(dict[str, object], value)
        kind, action = data.get("object_kind"), data.get("action")
    else:
        kind, action = getattr(value, "object_kind", None), getattr(value, "action", None)
    if isinstance(kind, str) and isinstance(action, str):
        return f"{kind}.{action}"
    return None


type SaveRequest = Annotated[
    Annotated[CreateDomainRequest, Tag("domain.create")]
    | Annotated[CreateKnowledgeRequest, Tag("kc.create")]
    | Annotated[UpdateKnowledgeRequest, Tag("kc.update")]
    | Annotated[DeleteKnowledgeRequest, Tag("kc.soft_delete")]
    | Annotated[CreateTaskRequest, Tag("task.create")]
    | Annotated[UpdateTaskRequest, Tag("task.update")]
    | Annotated[DeleteTaskRequest, Tag("task.soft_delete")],
    Discriminator(save_variant),
]


class CreateDomainResult(FactModel):
    object_ref: DomainRef
    content_ref: DomainContentRef
    gaps: list[Issue] = Field(default_factory=list[Issue])


class KnowledgeContentRef(FactModel):
    owner: Literal["domain"] = "domain"
    object_ref: KnowledgeRef
    path: Literal[""] = ""


class SaveKnowledgeResult(FactModel):
    object_ref: KnowledgeRef
    content_ref: KnowledgeContentRef
    gaps: list[Issue] = Field(default_factory=list[Issue])


class TaskContentRef(FactModel):
    owner: Literal["domain"] = "domain"
    object_ref: TaskRef
    path: Literal[""] = ""


class SaveTaskResult(FactModel):
    object_ref: TaskRef
    content_ref: TaskContentRef
    gaps: list[Issue]


type SaveResult = CreateDomainResult | SaveKnowledgeResult | SaveTaskResult


class CreateDomainResponse(FactModel):
    request_ref: UUID
    result: SaveResult


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


class MemberRow(FactModel):
    object_ref: MemberRef
    name: str
    is_deleted: bool
    source_event_id: UUID


class MemberList(FactModel):
    items: list[MemberRow]
    next_cursor: str | None
    read_token: str


class KnowledgeView(FactModel):
    object_ref: KnowledgeRef
    content: KnowledgeComponent
    content_ref: KnowledgeContentRef
    is_identity_deleted: bool
    source_refs: list[Ref] = Field(default_factory=list[Ref])
    source_event_id: UUID
    gaps: list[Issue] = Field(default_factory=list[Issue])


class KnowledgeDetail(FactModel):
    object: KnowledgeView


class TaskView(FactModel):
    object_ref: TaskRef
    content: TaskDefinition
    content_ref: TaskContentRef
    is_identity_deleted: bool
    source_refs: list[Ref] = Field(default_factory=list[Ref])
    source_event_id: UUID
    gaps: list[Issue]


class TaskDetail(FactModel):
    object: TaskView


type ObjectDetail = DomainDetail | KnowledgeDetail | TaskDetail


class DomainService(Protocol):
    """当前会话由入口核验，应用端口执行领域权限和范围判断。"""

    async def list_domains(self, session: SessionView) -> DomainList: ...

    async def list_members(
        self,
        session: SessionView,
        domain_id: UUID,
        name: str,
        cursor: str | None,
        limit: int,
        kinds: list[MemberKind] | None,
    ) -> MemberList: ...

    async def read_object(
        self,
        session: SessionView,
        domain_id: UUID,
        object_id: UUID,
        version: int | None = None,
    ) -> ObjectDetail: ...

    async def save_definition(
        self, session: SessionView, body: SaveRequest
    ) -> CreateDomainResponse: ...

    async def read_receipt(
        self, principal_id: UUID, session_id: UUID, query: ReceiptQuery
    ) -> ReceiptView[SaveResult]: ...
