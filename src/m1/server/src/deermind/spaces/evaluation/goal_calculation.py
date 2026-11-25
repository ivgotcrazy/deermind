"""按固定目标与已有作答观测派生达成状态，保留每项依据。"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import Ref
from deermind.product.public.learning_targets import GoalItem, TargetAspect
from deermind.spaces.domain.public import SolutionRef
from deermind.spaces.evaluation.public import (
    AspectDecision,
    Attainment,
    ClaimRef,
    Decision,
    GoalDecision,
    ItemDecision,
    MethodDecision,
)
from pydantic import JsonValue

THRESHOLD = Decimal("0.90")

type GoalKey = tuple[UUID, SolutionRef, str]
type BeliefKey = tuple[ClaimRef, SolutionRef, str]


@dataclass(frozen=True)
class CoveredAnswer:
    evidence_ref: Ref
    qualification: Literal["eligible", "ineligible", "unknown"]
    condition_values: Mapping[str, JsonValue]
    verified_scope: str | None = None


@dataclass(frozen=True)
class Observation:
    """Only assessment evidence contained in the same immutable mastery snapshot."""

    p_obs: Decimal | None
    covered_answers: Sequence[CoveredAnswer]


def _covers(required: Mapping[str, JsonValue], actual: Mapping[str, JsonValue]) -> bool:
    # 逐项核对要求条件：键须存在，且规范序列化后取值一致；任一不满足即不覆盖。
    return all(
        key in actual and canonical_json(actual[key]) == canonical_json(value)
        for key, value in required.items()
    )


def _aspect(
    item: GoalItem,
    method: SolutionRef,
    aspect: TargetAspect,
    gaps: Mapping[GoalKey, Sequence[str]],
    snapshot: Mapping[BeliefKey, Observation],
) -> AspectDecision:
    code = aspect.aspect_ref.aspect_code
    gap = gaps.get((item.item_id, method, code), ())
    # 该方面仍有未补的差距，直接判未准备，不再看观测概率。
    if gap:
        return AspectDecision(
            readiness="unprepared",
            attainment=None,
            reasons=list(gap),
            aspect_code=code,
            p_obs=None,
            evidence_refs=[],
        )
    observed = snapshot.get((item.claim_ref, method, code))
    # 无观测记录或观测概率缺失，达成状态记未知，仍算就绪待补证。
    if observed is None or observed.p_obs is None:
        return AspectDecision(
            readiness="ready",
            attainment="unknown",
            reasons=["no_observation"],
            aspect_code=code,
            p_obs=None,
            evidence_refs=list(
                dict.fromkeys(answer.evidence_ref for answer in observed.covered_answers)
            )
            if observed
            else [],
        )
    probability = observed.p_obs
    # 观测概率必须是有限值且落在 [0,1]，否则判记录非法。
    if not probability.is_finite() or not 0 <= probability <= 1:
        raise ValueError("Invalid observation probability")
    # 筛选有效佐证：答案须合格、条件取值与方面要求一致，且范围描述为空或与核验范围相同。
    covered = [
        answer.evidence_ref
        for answer in observed.covered_answers
        if (
            answer.qualification == "eligible"
            and _covers(aspect.condition_values, answer.condition_values)
            and (
                not item.task_conditions.description
                or item.task_conditions.description == answer.verified_scope
            )
        )
    ]
    # 无有效佐证记未知；有佐证再按概率是否达到 0.90 阈值区分达成或待加强。
    attainment: Attainment = (
        "unknown" if not covered else ("met" if probability >= THRESHOLD else "needs_strengthening")
    )
    # 按达成状态映射原因码；未知时再区分是有答案但条件未知，还是完全无观测。
    reason = {
        "unknown": "condition_unknown" if observed.covered_answers else "no_observation",
        "met": "threshold_met",
        "needs_strengthening": "below_threshold",
    }[attainment]
    return AspectDecision(
        readiness="ready",
        attainment=attainment,
        reasons=[reason],
        aspect_code=code,
        p_obs=probability,
        evidence_refs=list(
            dict.fromkeys(answer.evidence_ref for answer in observed.covered_answers)
        ),
    )


def _combine(children: Sequence[Decision], *, any_one: bool = False) -> Decision:
    # 无子节点可聚合，判定义缺失、未准备。
    if not children:
        return Decision(readiness="unprepared", attainment=None, reasons=["definition_missing"])
    states = [child.attainment for child in children]
    # 汇总各子节点原因码并去重，保留出现顺序。
    reasons = list(dict.fromkeys(reason for child in children for reason in child.reasons))
    # 任一通过模式下，只要有一个子节点达成，整体即达成。
    if any_one and "met" in states:
        return Decision(readiness="ready", attainment="met", reasons=reasons)
    # 存在未准备（None）的子节点，整体也判未准备。
    if None in states:
        return Decision(readiness="unprepared", attainment=None, reasons=reasons)
    # 任一通过：全部待加强才整体待加强；全部通过：任一待加强即整体待加强。
    if (any_one and all(state == "needs_strengthening" for state in states)) or (
        not any_one and "needs_strengthening" in states
    ):
        return Decision(readiness="ready", attainment="needs_strengthening", reasons=reasons)
    # 其余情况：仍含未知则记未知，否则整体达成。
    return Decision(
        readiness="ready", attainment="unknown" if "unknown" in states else "met", reasons=reasons
    )


def derive_target(
    items: Sequence[GoalItem],
    gaps: Mapping[GoalKey, Sequence[str]],
    snapshot: Mapping[BeliefKey, Observation],
) -> GoalDecision:
    """No I/O, numerical update, rounding, or new interpretation of prior answers."""
    result: list[ItemDecision] = []
    # 逐层聚合：目标项 → 解法 → 方面，先算方面决策再向上汇总。
    for item in items:
        methods: list[MethodDecision] = []
        for method in item.methods:
            # 计算该解法下每个方面的决策。
            aspects = [
                _aspect(item, method.method_ref, aspect, gaps, snapshot)
                for aspect in method.aspects
            ]
            summary = _combine(aspects)
            methods.append(
                MethodDecision(
                    **summary.model_dump(),
                    method_ref=method.method_ref,
                    aspects=aspects,
                )
            )
        result.append(
            ItemDecision(
                **_combine(methods, any_one=item.method_mode == "any_one").model_dump(),
                item_id=item.item_id,
                claim_ref=item.claim_ref,
                method_mode=item.method_mode,
                methods=methods,
            )
        )
    return GoalDecision(**_combine(result).model_dump(), items=result)
