"""领域管理的公开模型和应用端口。"""

from datetime import datetime
from typing import Annotated, Literal, Protocol, cast
from uuid import UUID

from pydantic import Discriminator, Field, JsonValue, StringConstraints, Tag, field_validator

from deermind.abstractions.events import FactModel, Ref
from deermind.foundation.system.public.errors import Issue
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.public.authentication import SessionView
from deermind.spaces.domain.rich_content import RichContent, SourceRef, invalid, paragraph

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
    "BookDomainService",
    "paragraph",
    "DomainView",
    "NonBlank",
    "RichContent",
    "SourceRef",
]

SAVE_ACTION = "domain.save_definition"
CONFIRM_PATH_ACTION = "domain.confirm_kc_path"

type NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
type RequestId = Annotated[str, Field(min_length=1, max_length=128)]
type Version = Annotated[int, Field(ge=1, le=2**63 - 1)]
type JsonUuid = Annotated[UUID, Field(strict=False)]
type MemberKind = Literal["kc", "task", "solution"]
type IntakeKind = Literal["kc", "task_instance", "reference"]


class IntakeView(FactModel):
    item_ref: Ref
    kind: IntakeKind
    title: str
    state: Literal["pending", "completed", "removed"]
    parent_ref: Ref | None
    result_ref: Ref | None


class IntakeList(FactModel):
    items: list[IntakeView]
    next_cursor: str | None
    read_token: str


class IntakeDetail(FactModel):
    item: IntakeView


class DomainIntakeQueries(Protocol):
    async def list_items(
        self,
        domain_id: UUID,
        kind: IntakeKind | None,
        cursor: str | None,
        limit: int,
        reader_id: UUID,
    ) -> IntakeList: ...

    async def detail(self, domain_id: UUID, item_id: UUID) -> IntakeDetail: ...

    async def find_material_parent(
        self,
        domain_id: UUID,
        import_id: UUID,
        candidate_id: UUID,
        revision: int,
    ) -> IntakeDetail: ...


class DomainRef(FactModel):
    kind: Literal["domain"] = "domain"
    object_id: JsonUuid
    version: Version


class KnowledgeRef(FactModel):
    kind: Literal["kc"]
    object_id: JsonUuid
    version: Version


class TaskRef(FactModel):
    kind: Literal["task"]
    object_id: JsonUuid
    version: Version


class SolutionRef(FactModel):
    kind: Literal["solution"]
    object_id: JsonUuid
    version: Version


type MemberRef = KnowledgeRef | TaskRef | SolutionRef
type ObjectRef = DomainRef | MemberRef


def definition_content(content: RichContent | None, title: str) -> RichContent | None:
    if content is None:
        # 可空字段直接放行。
        return None
    if content.role != "definition":
        invalid(title, ("role",), "此字段只能使用定义正文。")
    if content.source_refs:
        # 定义入口暂不允许挂外部来源。
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
            # 非空定义不得留空正文块。
            invalid(cls.__name__, ("blocks",), "请提供正文。")
        return definition_content(content, cls.__name__)


class Prerequisite(FactModel):
    task_ref: TaskRef
    reason: NonBlank
    applies_to: Literal["all", "specified"]
    method_refs: list[SolutionRef] = Field(default_factory=list[SolutionRef])


class MethodDependency(FactModel):
    task_ref: TaskRef
    reason: NonBlank


class TaskDefinition(FactModel):
    """可保存未填齐的定义；就绪要求与个人评价独立。"""

    name: NonBlank
    task_type: Literal["knowledge", "composite"] | None = None
    knowledge_ref: KnowledgeRef | None = None
    responsibility: RichContent | None = None
    expected_output: RichContent | None = None
    completion_conditions: RichContent | None = None
    applicability: RichContent | None = None
    boundaries: RichContent | None = None
    method_refs: list[SolutionRef] = Field(default_factory=list[SolutionRef])
    prerequisites: list[Prerequisite] = Field(default_factory=list[Prerequisite])

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
            # 所有段落都是空文本时，视为未填。
            invalid(cls.__name__, ("blocks",), "请提供正文，未填项请留空。")
        return definition_content(content, cls.__name__)


def task_gaps(content: TaskDefinition) -> list[Issue]:
    fields = (
        ("responsibility", content.responsibility, "认知责任"),
        ("expected_output", content.expected_output, "预期表现"),
        ("completion_conditions", content.completion_conditions, "完成条件"),
        ("applicability", content.applicability, "适用条件"),
        ("boundaries", content.boundaries, "适用边界"),
    )
    gaps = [
        Issue(code="missing_content", path=f"/{field}", message=f"请补充{label}。")
        for field, value, label in fields
        if value is None
    ]
    if not content.method_refs:
        # 任务未关联任何方法，记缺口。
        gaps.append(Issue(code="missing_methods", path="/method_refs", message="尚未关联方法。"))
    return gaps


class SolutionDefinition(FactModel):
    """方法描述本层思路、依据、适用条件和关键过程。"""

    name: NonBlank
    dependencies: list[MethodDependency] | None = None
    approach: RichContent | None = None
    rationale: RichContent | None = None
    applicability: RichContent | None = None
    key_process: RichContent | None = None
    kc_refs: list[KnowledgeRef] = Field(default_factory=list[KnowledgeRef])

    @field_validator("approach", "rationale", "applicability", "key_process")
    @classmethod
    def validate_content(cls, content: RichContent | None) -> RichContent | None:
        if content is not None and not content.blocks:
            invalid(cls.__name__, ("blocks",), "请提供正文，未填项请留空。")
        return definition_content(content, cls.__name__)


def solution_gaps(content: SolutionDefinition) -> list[Issue]:
    fields = (
        ("approach", content.approach, "方法思路"),
        ("rationale", content.rationale, "方法依据"),
        ("applicability", content.applicability, "适用条件"),
        ("key_process", content.key_process, "关键过程"),
    )
    gaps = [
        Issue(code="missing_content", path=f"/{field}", message=f"请补充{label}。")
        for field, value, label in fields
        if value is None
    ]
    if content.dependencies is None and not content.kc_refs:
        # 方法未关联知识成分，记缺口。
        gaps.append(Issue(code="missing_knowledge", path="/kc_refs", message="尚未关联知识成分。"))
    return gaps


type DefinitionContent = DomainDefinition | KnowledgeComponent | TaskDefinition | SolutionDefinition


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


class DeleteDomainRequest(FactModel):
    request_id: RequestId
    object_kind: Literal["domain"]
    action: Literal["soft_delete"]
    object_ref: DomainRef
    expected_version: Version
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
    candidate_ref: Ref | None = None


class UpdateTaskRequest(_TaskRequest):
    action: Literal["update"]
    object_ref: TaskRef
    expected_version: Version
    definition: TaskDefinition


class DeleteTaskRequest(_TaskRequest):
    action: Literal["soft_delete"]
    object_ref: TaskRef
    expected_version: Version


class _SolutionRequest(FactModel):
    request_id: RequestId
    object_kind: Literal["solution"]
    change_note: NonBlank


class CreateSolutionRequest(_SolutionRequest):
    action: Literal["create"]
    domain_id: JsonUuid
    definition: SolutionDefinition
    candidate_ref: Ref | None = None


class UpdateSolutionRequest(_SolutionRequest):
    action: Literal["update"]
    object_ref: SolutionRef
    expected_version: Version
    definition: SolutionDefinition


class DeleteSolutionRequest(_SolutionRequest):
    action: Literal["soft_delete"]
    object_ref: SolutionRef
    expected_version: Version


def save_variant(value: object) -> str | None:
    """同时以对象种类和动作定位唯一请求模型。"""
    if isinstance(value, dict):
        data = cast(dict[str, object], value)
        kind, action = data.get("object_kind"), data.get("action")
    else:
        kind, action = getattr(value, "object_kind", None), getattr(value, "action", None)
    if isinstance(kind, str) and isinstance(action, str):
        # 种类+动作拼成判别标签。
        return f"{kind}.{action}"
    return None


type SaveRequest = Annotated[
    Annotated[CreateDomainRequest, Tag("domain.create")]
    | Annotated[DeleteDomainRequest, Tag("domain.soft_delete")]
    | Annotated[CreateKnowledgeRequest, Tag("kc.create")]
    | Annotated[UpdateKnowledgeRequest, Tag("kc.update")]
    | Annotated[DeleteKnowledgeRequest, Tag("kc.soft_delete")]
    | Annotated[CreateTaskRequest, Tag("task.create")]
    | Annotated[UpdateTaskRequest, Tag("task.update")]
    | Annotated[DeleteTaskRequest, Tag("task.soft_delete")]
    | Annotated[CreateSolutionRequest, Tag("solution.create")]
    | Annotated[UpdateSolutionRequest, Tag("solution.update")]
    | Annotated[DeleteSolutionRequest, Tag("solution.soft_delete")],
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


class SolutionContentRef(FactModel):
    owner: Literal["domain"] = "domain"
    object_ref: SolutionRef
    path: Literal[""] = ""


class SaveSolutionResult(FactModel):
    object_ref: SolutionRef
    content_ref: SolutionContentRef
    gaps: list[Issue]


type SaveResult = CreateDomainResult | SaveKnowledgeResult | SaveTaskResult | SaveSolutionResult


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


class SolutionView(FactModel):
    object_ref: SolutionRef
    content: SolutionDefinition
    content_ref: SolutionContentRef
    is_identity_deleted: bool
    source_refs: list[Ref] = Field(default_factory=list[Ref])
    source_event_id: UUID
    gaps: list[Issue]


class SolutionDetail(FactModel):
    object: SolutionView


type ObjectDetail = DomainDetail | KnowledgeDetail | TaskDetail | SolutionDetail


class KnowledgeUse(FactModel):
    method_ref: SolutionRef
    kc_ref: KnowledgeRef


class KnowledgeSources(FactModel):
    kc_id: UUID
    uses: list[KnowledgeUse]


class ConfirmKCPathRequest(FactModel):
    request_id: RequestId
    kc_ref: KnowledgeRef
    task_ref: TaskRef
    solution_ref: SolutionRef
    observable_behavior: NonBlank
    insufficient_examples: Annotated[list[NonBlank], Field(min_length=1)]
    not_direct_reason: NonBlank | None = None


class ConfirmKCPathResult(FactModel):
    confirmation_ref: Ref


class ConfirmKCPathResponse(FactModel):
    request_ref: UUID
    result: ConfirmKCPathResult


class KCPathView(FactModel):
    confirmation_ref: Ref
    basis_ref: Ref
    kc_ref: KnowledgeRef
    task_ref: TaskRef
    solution_ref: SolutionRef
    observable_behavior: str
    insufficient_examples: list[str]
    confirmed_by: Ref
    confirmed_at: datetime
    source_event_id: UUID


class TaskDependencies(FactModel):
    task_ref: TaskRef
    method_refs: list[SolutionRef]
    kc_refs: list[KnowledgeRef]
    kc_sources: list[KnowledgeSources]
    prerequisites: list[Prerequisite]
    gaps: list[Issue]
    kc_test_paths: list[KCPathView]


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

    async def read_dependencies(
        self,
        session: SessionView,
        domain_id: UUID,
        task_id: UUID,
        version: int,
        solution_ids: list[UUID] | None,
    ) -> TaskDependencies: ...

    async def read_receipt(
        self, principal_id: UUID, session_id: UUID, query: ReceiptQuery
    ) -> ReceiptView[SaveResult]: ...

    async def confirm_kc_path(
        self, session: SessionView, domain_id: UUID, body: ConfirmKCPathRequest
    ) -> ConfirmKCPathResponse: ...

    async def read_path_receipt(
        self, principal_id: UUID, session_id: UUID, query: ReceiptQuery
    ) -> ReceiptView[ConfirmKCPathResult]: ...


EXTRACT = "domain.extract_template"
CLASSIFY = "domain.classify_instance"

type ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1200)
]
type SubjectKind = Literal["task", "solution"]


class ExtractDefinition(FactModel):
    request_id: RequestId
    intake_item_ref: Ref
    template_kind: SubjectKind
    extraction_instruction: ShortText | None = None
    prior_candidate_ref: Ref | None = None


class CheckClassification(FactModel):
    request_id: RequestId
    intake_item_ref: Ref
    task_ref: TaskRef
    solution_ref: SolutionRef | None = None
    confirm_add_method: bool = False


class AnalysisAcceptance(FactModel):
    request_ref: UUID
    operation_run_id: UUID


class Finding(FactModel):
    criterion: ShortText
    conclusion: ShortText
    material_locations: list[ShortText] = Field(max_length=12)
    definition_locations: list[ShortText] = Field(max_length=12)


class Assessment(FactModel):
    candidate_key: ShortText
    findings: list[Finding] = Field(max_length=12)
    issues: list[ShortText] = Field(max_length=12)
    result: Literal["matched", "mismatch", "unresolved"]


class DraftDefinition(FactModel):
    kind: SubjectKind
    name: ShortText
    responsibility: ShortText | None = None
    expected_output: ShortText | None = None
    completion_conditions: ShortText | None = None
    boundaries: ShortText | None = None
    applicability: ShortText | None = None
    approach: ShortText | None = None
    rationale: ShortText | None = None
    key_process: ShortText | None = None
    evidence: list[ShortText] = Field(max_length=12)


class AnalysisOutput(FactModel):
    draft: DraftDefinition | None
    results: list[Assessment] = Field(max_length=10)
    unresolved: list[ShortText] = Field(max_length=12)


class AnalysisReceipt(FactModel):
    candidate_ref: Ref | None
    check_ref: Ref
    proposed_definition: dict[str, JsonValue] | None
    output: AnalysisOutput


class AnalysisArtifactView(FactModel):
    artifact: dict[str, JsonValue]


class DomainAnalysisService(Protocol):
    async def accept(
        self,
        domain_id: UUID,
        principal: UUID,
        command: "ExtractDefinition | CheckClassification | CheckManualInstance",
    ) -> AnalysisAcceptance: ...

    async def artifact(self, domain_id: UUID, identity: UUID) -> AnalysisArtifactView: ...


PROCESS_INTAKE = "domain.process_intake"
SAVE_INSTANCE = "domain.save_instance"


class InstanceRef(FactModel):
    kind: Literal["task_instance"] = "task_instance"
    object_id: JsonUuid
    version: Version

    def reference(self) -> Ref:
        return Ref(owner="domain", type=self.kind, id=str(self.object_id), version=self.version)


class ReferenceSolution(FactModel):
    reference_id: JsonUuid
    solution_ref: SolutionRef
    content: RichContent
    origin: Literal["textbook", "system_generated", "admin_authored"]
    source_refs: list[SourceRef]


class TaskInstance(FactModel):
    title: NonBlank
    task_ref: TaskRef
    statement: RichContent
    answer_basis: RichContent | None
    reference_solutions: list[ReferenceSolution]
    source_refs: list[SourceRef]


class CheckManualInstance(FactModel):
    request_id: RequestId
    instance: TaskInstance
    object_ref: InstanceRef | None = None


class IntakeAction(FactModel):
    request_id: RequestId
    expected_revision: Version
    action: Literal["add_kc", "associate_task", "associate_solution", "discard"]
    definition: KnowledgeComponent | None = None
    existing_kc_ref: KnowledgeRef | None = None
    task_ref: TaskRef | None = None
    existing_instance_ref: InstanceRef | None = None
    solution_ref: SolutionRef | None = None
    task_instance_ref: InstanceRef | None = None
    expected_version: Version | None = None
    classification_check_ref: Ref | None = None
    confirm_add_method: bool = False
    expected_task_version: Version | None = None
    confirm_discard_children: bool = False


class IntakeActionResult(FactModel):
    item_ref: Ref
    state: Literal["added", "associated", "discarded"]
    object_ref: Ref | None
    reference_ref: Ref | None
    check_refs: list[Ref]
    affected_item_refs: list[Ref]
    group_pending_count: int


class IntakeActionReceipt(FactModel):
    request_ref: UUID
    result: IntakeActionResult


class InstanceCommand(FactModel):
    request_id: RequestId
    action: Literal["create", "update", "soft_delete"]
    instance: TaskInstance | None = None
    object_ref: InstanceRef | None = None
    expected_version: Version | None = None
    change_note: NonBlank
    classification_check_ref: Ref | None = None


class InstanceView(FactModel):
    instance_ref: InstanceRef
    content: TaskInstance
    is_deleted: bool


class InstanceReceipt(FactModel):
    request_ref: UUID
    result: InstanceView


class InstanceList(FactModel):
    items: list[InstanceView]
    next_cursor: str | None


class DomainInstanceService(Protocol):
    async def list_instances(
        self,
        domain_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> InstanceList: ...

    async def read(self, domain_id: UUID, identity: UUID, version: int | None) -> InstanceView: ...

    async def save(
        self,
        domain_id: UUID,
        principal: UUID,
        command: InstanceCommand,
    ) -> InstanceReceipt: ...


class DomainIntakeActions(Protocol):
    async def process(
        self,
        domain_id: UUID,
        item_id: UUID,
        principal: UUID,
        command: IntakeAction,
    ) -> IntakeActionReceipt: ...

    async def read_parent(self, domain_id: UUID, item_id: UUID) -> InstanceView: ...


class BookDomainService[Tx](DomainService, Protocol):
    async def publish_members(
        self,
        db: Tx,
        domain: UUID,
        actor: Ref,
        request: UUID,
        edition: UUID,
        members: list[tuple[MemberRef, DefinitionContent]],
        paths: list[ConfirmKCPathRequest],
    ) -> None: ...

    async def lock_active_domain(self, connection: Tx, domain_id: UUID) -> None: ...
