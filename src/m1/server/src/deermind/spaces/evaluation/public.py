"""评价定义及其管理合同。"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Protocol
from uuid import UUID

from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import FactModel, Ref
from deermind.foundation.system.files.uploads import JsonUUID
from deermind.foundation.system.public.errors import Issue
from deermind.product.public.materials import RequestId, Revision
from deermind.spaces.domain.public import SolutionRef, TaskRef
from pydantic import Field, JsonValue, StringConstraints

MANAGE_CLAIM = "evaluation.manage_claim"
STANDARD_ASPECTS = {
    "independent": "独立完成",
    "understanding": "理解与解释",
    "transfer": "迁移",
    "retention": "保持",
}
type Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
type Explanation = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)
]
type AspectCode = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]


class ClaimRef(FactModel):
    claim_id: JsonUUID
    revision: Revision


class AspectDefinition(FactModel):
    code: AspectCode
    label: Title
    description: Explanation
    change_reason: Explanation | None = None


class CriterionFields(FactModel):
    title: Title
    required_inputs: list[Explanation]
    judgement_basis: Explanation
    pass_description: Explanation
    fail_description: Explanation
    unknown_description: Explanation


class CriterionDraft(CriterionFields):
    criterion_id: JsonUUID | None = None


class ExecutionCriterion(CriterionFields):
    criterion_id: JsonUUID


class AspectRule(FactModel):
    aspect_code: AspectCode
    judgement_basis: Explanation
    evidence_requirements: list[Explanation]
    condition_schema: dict[str, JsonValue]
    default_values: dict[str, JsonValue]


class MethodDefinition(FactModel):
    method_ref: SolutionRef
    criterion_ids: list[JsonUUID]
    aspect_rules: list[AspectRule]


class ClaimDefinition(FactModel):
    domain_id: JsonUUID
    task_ref: TaskRef
    title: Title
    description: Explanation
    aspects: list[AspectDefinition] = Field(min_length=1)
    criteria: list[ExecutionCriterion]
    methods: list[MethodDefinition]


class CreateClaim(FactModel):
    request_id: RequestId
    action: Literal["create_claim"]
    domain_id: JsonUUID
    task_ref: TaskRef
    title: Title
    description: Explanation
    aspects: list[AspectDefinition] = Field(min_length=1)


class ReviseClaim(FactModel):
    request_id: RequestId
    domain_id: JsonUUID
    task_ref: TaskRef
    claim_id: JsonUUID
    expected_revision: Revision


class SaveClaim(ReviseClaim):
    action: Literal["save_claim"]
    title: Title
    description: Explanation
    aspects: list[AspectDefinition] = Field(min_length=1)


class SaveCriterion(ReviseClaim):
    action: Literal["save_criterion"]
    criterion: CriterionDraft


class SetMethodCriteria(ReviseClaim):
    action: Literal["set_method_criteria"]
    method_ref: SolutionRef
    criterion_ids: list[JsonUUID]


class SaveAspectRule(ReviseClaim):
    action: Literal["save_aspect_rule"]
    method_ref: SolutionRef
    rule: AspectRule


class RemoveCriterion(ReviseClaim):
    action: Literal["remove_criterion"]
    criterion_id: JsonUUID


type ClaimCommand = Annotated[
    CreateClaim | SaveClaim | SaveCriterion | SetMethodCriteria | SaveAspectRule | RemoveCriterion,
    Field(discriminator="action"),
]


class ClaimRow(FactModel):
    claim_ref: ClaimRef
    task_ref: TaskRef
    title: str
    gaps: list[Issue]


class ClaimList(FactModel):
    items: list[ClaimRow]
    next_cursor: str | None


class ClaimView(FactModel):
    claim_ref: ClaimRef
    definition: ClaimDefinition
    gaps: list[Issue]


class ClaimDetail(FactModel):
    claim: ClaimView


class ClaimResult(FactModel):
    claim_ref: ClaimRef
    changed: bool
    gaps: list[Issue]
    affected_method_refs: list[SolutionRef]


class ClaimReceipt(FactModel):
    request_ref: UUID
    result: ClaimResult


class ClaimService(Protocol):
    async def list_claims(
        self,
        principal: UUID,
        domain_id: UUID,
        task_id: UUID | None,
        name: str,
        cursor: str | None,
        limit: int,
    ) -> ClaimList: ...

    async def detail(self, claim_id: UUID, revision: int | None) -> ClaimDetail: ...

    async def save(self, principal: UUID, command: ClaimCommand) -> ClaimReceipt: ...


type Attainment = Literal["met", "needs_strengthening", "unknown"]
type Readiness = Literal["ready", "unprepared"]


class Decision(FactModel):
    readiness: Readiness
    attainment: Attainment | None
    reasons: list[str]


class AspectDecision(Decision):
    aspect_code: str
    p_obs: Decimal | None
    evidence_refs: list[Ref]


class MethodDecision(Decision):
    method_ref: SolutionRef
    aspects: list[AspectDecision]


class ItemDecision(Decision):
    item_id: UUID
    claim_ref: ClaimRef
    method_mode: Literal["specified", "any_one", "each"]
    methods: list[MethodDecision]


class GoalDecision(Decision):
    items: list[ItemDecision]


class GoalEvaluation(FactModel):
    goal_evaluation_id: UUID
    scope_id: UUID
    trigger_event_id: UUID
    input_ref: UUID
    target_basis_ref: UUID
    result: GoalDecision
    previous_current_ref: UUID | None
    current_state_applied: bool
    created_at: datetime


class EvidenceSummary(FactModel):
    evidence_ref: Ref
    aspect_code: str
    qualification: str
    verdict: str | None
    reason: str
    source_event_refs: list[UUID]


class EvidenceQuote(FactModel):
    ref: EventPartRef
    quote: str


class BeliefChange(FactModel):
    update_kind: Literal["observation", "learning_transition"]
    p_obs_before: float | None = None
    p_obs_after: float | None = None
    p_current_before: float
    p_current_after: float
    parameter_ref: str
    algorithm_ref: str


class EvidenceView(FactModel):
    evidence_id: UUID
    aspect_code: str
    qualification: str
    verdict: str | None = None
    reason: str
    reason_codes: list[str]
    source_refs: list[EventPartRef]
    source_spans: list[EvidenceQuote]
    belief_change: BeliefChange | None = None


class BeliefView(FactModel):
    p_obs: float | None = None
    p_current: float
    last_observed_at: datetime | None = None
    belief_revision_ref: Ref | None = None
    observation_status: Literal["observed", "unknown"]
    unknown_reasons: list[str]


class SourceExcerpt(FactModel):
    event_id: UUID
    content: list[JsonValue]


class BasisView(FactModel):
    view: Literal["target", "belief", "evidence", "event", "processing"]
    basis_ref: Ref | None = None
    items: list[EvidenceSummary] | None = None
    next_cursor: str | None = None
    evidence: EvidenceView | None = None
    source: SourceExcerpt | None = None
    belief: BeliefView | None = None
    processing: Literal["not_found", "pending", "completed", "failed"] | None = None


class EvaluationBasisService(Protocol):
    async def target(
        self, scope: UUID, identity: UUID, item: UUID, after: UUID | None, limit: int
    ) -> BasisView: ...

    async def evidence(self, scope: UUID, identity: UUID, origin: UUID | None) -> BasisView: ...

    async def from_event(
        self, scope: UUID, event: UUID, after: UUID | None, limit: int
    ) -> BasisView: ...

    async def belief(
        self,
        scope: UUID,
        snapshot: UUID,
        claim: UUID,
        revision: int,
        method: UUID,
        version: int,
        aspect: str,
        after: UUID | None,
        limit: int,
    ) -> BasisView: ...

    async def processing(self, scope: UUID, trigger: UUID) -> BasisView: ...
