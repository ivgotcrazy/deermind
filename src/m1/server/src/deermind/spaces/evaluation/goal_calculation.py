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
    if not probability.is_finite() or not 0 <= probability <= 1:
        raise ValueError("Invalid observation probability")
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
    attainment: Attainment = (
        "unknown" if not covered else ("met" if probability >= THRESHOLD else "needs_strengthening")
    )
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
    if not children:
        return Decision(readiness="unprepared", attainment=None, reasons=["definition_missing"])
    states = [child.attainment for child in children]
    reasons = list(dict.fromkeys(reason for child in children for reason in child.reasons))
    if any_one and "met" in states:
        return Decision(readiness="ready", attainment="met", reasons=reasons)
    if None in states:
        return Decision(readiness="unprepared", attainment=None, reasons=reasons)
    if (any_one and all(state == "needs_strengthening" for state in states)) or (
        not any_one and "needs_strengthening" in states
    ):
        return Decision(readiness="ready", attainment="needs_strengthening", reasons=reasons)
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
    for item in items:
        methods: list[MethodDecision] = []
        for method in item.methods:
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
