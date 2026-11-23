"""活动配置保存、固定读取及可选草稿缺口的公开合同。"""

from typing import Annotated, Literal, Protocol
from uuid import UUID

from deermind.abstractions.events import FactModel, Ref
from deermind.foundation.system.files.uploads import JsonUUID
from deermind.foundation.system.public.errors import Issue
from deermind.product.public.materials import RequestId, Revision
from pydantic import Field, StringConstraints

MANAGE_ACTIVITY = "interaction.manage_activity_config"
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
