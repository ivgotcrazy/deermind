"""活动配置保存、固定读取及可选草稿缺口的公开合同。"""

from datetime import datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID

from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import FactModel, Ref
from deermind.foundation.system.files.uploads import JsonUUID
from deermind.foundation.system.public.errors import Issue
from deermind.product.public.authentication import AccountView
from deermind.product.public.materials import RequestId, Revision
from deermind.spaces.domain.public import RichContent
from pydantic import AwareDatetime, Field, JsonValue, StringConstraints, model_validator

MANAGE_ACTIVITY = "interaction.manage_activity_config"
CONTROL_ACTIVITY = "interaction.control_activity"
HANDLE_INPUT = "interaction.handle_input"
SUBMIT_ANSWER = "interaction.submit_answer"
PREPARE_DETECTION = "interaction.prepare_detection"


type EvaluationMaterialRole = Literal[
    "answer",
    "help_basis",
    "question",
    "round_opened",
    "round_closed",
    "help",
    "provided_help",
    "prior_question",
    "teaching",
    "closure",
]


class EvaluationMaterial(FactModel):
    role: EvaluationMaterialRole
    ref: EventPartRef
    sha256: str
    content: JsonValue


class EvaluationSource(FactModel):
    scope_id: UUID
    trigger_event_id: UUID
    source_seq: int
    source_kind: Literal["answer", "teaching"]
    source_id: UUID
    adoption_ref: Ref
    activity_ref: Ref
    task_use_ref: Ref | None
    round_ref: Ref | None
    plan_ref: Ref | None
    task_instance_ref: Ref | None
    occurred_at: AwareDatetime
    materials: list[EvaluationMaterial]
    missing_reasons: list[str]


type ActivityType = Literal["explanation", "question_answer", "detection", "free_chat"]
type ConfigKind = Literal["blueprint", "rule", "strategy", "binding"]
type Wording = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)
]
type NodeId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
type Action = Literal[
    "reply",
    "clarify",
    "wait_input",
    "start_child",
    "prepare_detection",
    "start_detection",
    "continue_detection",
    "record_answer",
    "return_parent",
    "pause",
    "finish",
    "switch",
]


type RunState = Literal["active", "waiting_child", "paused", "completed", "cancelled", "blocked"]
type ControlAction = Literal["pause", "resume", "finish"]
type DirectoryView = Literal["current", "activity_tree", "messages"]


class ActivityRef(FactModel):
    """固定活动运行修订。"""

    activity_id: JsonUUID
    revision: Revision


class ActivityView(FactModel):
    """目录和当前路径共同使用的活动摘要。"""

    activity_ref: ActivityRef
    type: ActivityType
    name: str
    started_at: datetime
    parent_id: UUID | None
    root_id: UUID
    node_id: str
    run_state: RunState
    first_message_ref: UUID
    has_children: bool


class TextPart(FactModel):
    """消息中的原样文字。"""

    part_id: str
    type: Literal["text"]
    text: str


class ActivityNotice(FactModel):
    """已保存的活动变动提示。"""

    part_id: str
    type: Literal["activity_notice"]
    text: str


class QuestionPart(FactModel):
    """题目卡片固定本次使用身份，练习和正式检测只带题面。"""

    part_id: str
    type: Literal["question"]
    title: str
    purpose: Literal["example", "practice", "detection"]
    task_use_ref: Ref
    statement: RichContent
    worked_solution: RichContent | None = None

    @model_validator(mode="after")
    def check_visibility(self) -> "QuestionPart":
        if self.statement.role != "statement" or (
            self.worked_solution is not None
            and (self.purpose != "example" or self.worked_solution.role != "reference")
        ):
            raise ValueError("Question card cannot expose a reference answer")
        return self


class DetectionPlanPart(FactModel):
    part_id: str
    type: Literal["detection_plan"]
    plan_ref: Ref
    question_count: int
    gaps: list[str]


type MessagePart = Annotated[
    TextPart | ActivityNotice | QuestionPart | DetectionPlanPart, Field(discriminator="type")
]


class MessageView(FactModel):
    """正式提供的聊天消息。"""

    message_id: UUID
    message_seq: int
    role: Literal["student", "assistant", "system"]
    parts: list[MessagePart]
    activity_ref: ActivityRef | None
    committed_at: datetime


class DetectionPlanRef(FactModel):
    plan_id: JsonUUID
    revision: Revision


class DetectionRoundView(FactModel):
    round_ref: Ref
    task_use_ref: Ref
    plan_ref: DetectionPlanRef
    state: Literal["open", "paused", "closed"]
    can_continue: bool


class CurrentConversation(FactModel):
    """当前活动与正在处理的输入。"""

    current_activity: ActivityView | None
    path: list[ActivityView]
    active_input_id: UUID | None
    allowed_actions: list[ControlAction]
    latest_message_seq: int
    current_round: DetectionRoundView | None = None


class CurrentView(FactModel):
    current: CurrentConversation


class ActivityPage(FactModel):
    items: list[ActivityView]
    next_cursor: str | None


class MessagePage(FactModel):
    items: list[MessageView]
    next_cursor: str | None
    last_seq: int
    upper_seq: int


class ActivityCommand(FactModel):
    """暂停、恢复或结束固定修订。"""

    request_id: RequestId
    activity_ref: ActivityRef
    expected_activity_revision: Revision
    action: ControlAction


class OpenDetectionRound(FactModel):
    request_id: RequestId
    action: Literal["start_detection", "continue_detection"]
    activity_ref: ActivityRef
    expected_activity_revision: Revision
    plan_ref: DetectionPlanRef


class ActivityControlResult(FactModel):
    current: CurrentConversation
    outcome: Literal["changed", "stopped", "already_committed"]
    committed_refs: list[Ref]


class ActivityControlReceipt(FactModel):
    request_ref: UUID
    result: ActivityControlResult


class StudentInput(FactModel):
    """保持实际输入原文，当前浏览位置不进入引用。"""

    text: str | None
    attachment_refs: list[JsonUUID]
    explicit_refs: list[Ref]

    @model_validator(mode="after")
    def require_content(self) -> "StudentInput":
        if not (self.text and self.text.strip()) and not self.attachment_refs:
            raise ValueError("请输入消息或附上材料。")
        return self


class LearningInputCommand(FactModel):
    """学生消息首次送达和受理不明时使用同一请求编号。"""

    request_id: RequestId
    input: StudentInput


class LearningInputAcceptance(FactModel):
    """输入及后台工作已经共同保存。"""

    request_ref: UUID
    execution_ref: UUID
    input_id: UUID


class RetryLearningWork(FactModel):
    request_id: RequestId
    execution_ref: JsonUUID


class AnswerInput(FactModel):
    text: Wording


class AnswerCommand(FactModel):
    request_id: RequestId
    submission_id: JsonUUID
    task_use_ref: Ref
    activity_ref: ActivityRef
    round_ref: Ref | None
    expected_round_revision: Revision | None = None
    answer: AnswerInput


class PrepareDetectionCommand(FactModel):
    request_id: RequestId


class AnswerReceipt(FactModel):
    request_ref: UUID
    submission_ref: Ref
    event_ref: UUID
    round_state: Literal["closed"] | None = None
    result_keys: list[Ref] = Field(default_factory=list[Ref])
    feedback_runtime_ref: UUID


class StopReply(FactModel):
    """停止当前输入继续提交结果，保留已经保存的事实。"""

    request_id: RequestId
    action: Literal["stop_reply"]
    target_input_id: JsonUUID


class LearningTurnResult(FactModel):
    """固定已保存的当前回复和此次输入的结束结果。"""

    input_id: UUID
    message_refs: list[UUID]
    current: CurrentConversation
    outcome: Literal["completed", "needs_input", "blocked", "failed", "cancelled"]


class StudentTurnService(Protocol):
    async def prepare_detection(
        self,
        account: AccountView,
        scope: UUID,
        command: PrepareDetectionCommand,
    ) -> LearningInputAcceptance: ...
    async def submit_answer(
        self, account: AccountView, scope: UUID, command: AnswerCommand
    ) -> AnswerReceipt: ...

    async def accept(
        self, account: AccountView, scope: UUID, command: LearningInputCommand
    ) -> LearningInputAcceptance: ...

    async def stop(
        self, account: AccountView, scope: UUID, command: StopReply
    ) -> ActivityControlReceipt: ...

    async def retry(
        self, account: AccountView, scope: UUID, command: RetryLearningWork
    ) -> LearningInputAcceptance: ...

    async def check_space(self, account: AccountView, scope: UUID) -> None: ...


class DetectionRoundService(Protocol):
    async def open(
        self,
        account: AccountView,
        scope: UUID,
        command: OpenDetectionRound,
    ) -> ActivityControlReceipt: ...


class PresentationCommand(FactModel):
    presentation_id: JsonUUID
    surface: Literal["chat", "history", "textbook"]
    resource_ref: Ref
    content_part_refs: Annotated[list[Ref], Field(max_length=32)]
    client_reported_at: Annotated[AwareDatetime, Field(strict=False)] | None = None


class PresentationReceipt(FactModel):
    presentation_ref: Ref
    received_at: datetime


class ConversationService(Protocol):
    """按获准空间查询和变更活动。"""

    async def read(
        self,
        account: AccountView,
        scope: UUID,
        view: DirectoryView,
        *,
        activity: UUID | None,
        anchor: UUID | None,
        after: int,
        cursor: str | None,
        limit: int,
    ) -> CurrentView | ActivityPage | MessagePage: ...

    async def control(
        self, account: AccountView, scope: UUID, command: ActivityCommand
    ) -> ActivityControlReceipt: ...

    async def record_presentation(
        self, account: AccountView, scope: UUID, command: PresentationCommand
    ) -> PresentationReceipt: ...


class Fallback(FactModel):
    action: Literal["clarify", "wait_input", "blocked"]
    explanation: Wording


class BlueprintNode(FactModel):
    node_id: NodeId
    name: Wording
    purpose: Wording
    required_inputs: list[Wording]
    execution_guidance: Wording
    outputs: list[Wording]
    allowed_actions: list[Action]
    fallback: Fallback


class RequiredFact(FactModel):
    code: Literal[
        "plan_confirmed", "round_closed", "plan_has_next", "child_finished", "result_ready"
    ]
    value: bool


class Transition(FactModel):
    transition_id: NodeId
    source_node_id: NodeId
    target_node_id: NodeId
    order: Annotated[int, Field(ge=1)]
    when: Literal[
        "on_enter", "on_input", "after_reply", "on_child_return", "on_result", "on_control"
    ]
    condition_text: Wording | None = None
    required_facts: list[RequiredFact]
    evidence_required: bool


class BlueprintDefinition(FactModel):
    activity_type: ActivityType
    nodes: list[BlueprintNode] = Field(min_length=2)
    transitions: list[Transition]


class RuleDefinition(FactModel):
    activity_type: ActivityType
    name: Wording
    applies_when: Wording
    requirement: Wording
    basis: Wording
    limitations: list[Wording]
    enabled: bool


class StrategyDefinition(FactModel):
    activity_type: ActivityType
    name: Wording
    purpose: Wording
    applicability: Wording
    materials: list[Wording]
    approach: Wording
    adaptation: Wording
    finish_conditions: Wording
    enabled: bool


class LocalBinding(FactModel):
    rule_ids: list[JsonUUID]
    strategy_ids: list[JsonUUID]


class BindingDefinition(FactModel):
    activity_type: ActivityType
    activity: LocalBinding
    nodes: dict[NodeId, LocalBinding]


class SaveBase(FactModel):
    request_id: RequestId
    config_ref: Ref | None
    expected_revision: Revision | None


class SaveBlueprint(SaveBase):
    config_kind: Literal["blueprint"]
    definition: BlueprintDefinition


class SaveRule(SaveBase):
    config_kind: Literal["rule"]
    definition: RuleDefinition


class SaveStrategy(SaveBase):
    config_kind: Literal["strategy"]
    definition: StrategyDefinition


class SaveBinding(SaveBase):
    config_kind: Literal["binding"]
    definition: BindingDefinition


type ConfigCommand = Annotated[
    SaveBlueprint | SaveRule | SaveStrategy | SaveBinding, Field(discriminator="config_kind")
]


class BoundRule(FactModel):
    ref: Ref
    definition: RuleDefinition


class BoundStrategy(FactModel):
    ref: Ref
    definition: StrategyDefinition


class ResolvedActivityConfig(FactModel):
    activity_type: ActivityType
    blueprint_ref: Ref
    binding_ref: Ref
    blueprint: BlueprintDefinition
    binding: BindingDefinition
    rules: list[BoundRule]
    strategies: list[BoundStrategy]


class ConfigView(FactModel):
    config_ref: Ref
    definition: ResolvedActivityConfig
    gaps: list[Issue]
    usage_refs: list[Ref]


class ConfigResult(FactModel):
    config_ref: Ref
    definition_ref: Ref
    affected_refs: list[Ref]
    gaps: list[Issue]


class ConfigReceipt(FactModel):
    request_ref: UUID
    result: ConfigResult


class ActivityConfigService(Protocol):
    async def detail(self, activity_type: ActivityType, config_id: UUID | None) -> ConfigView: ...
    async def save(
        self, principal: UUID, activity_type: ActivityType, body: ConfigCommand
    ) -> ConfigReceipt: ...
