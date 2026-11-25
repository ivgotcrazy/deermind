"""结构化表现解释及确定性资格检查。"""

from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import FactModel, Ref
from deermind.spaces.domain.public import SolutionRef
from deermind.spaces.evaluation.inputs import EvaluationMaterials
from deermind.spaces.evaluation.public import STANDARD_ASPECTS, ClaimRef
from deermind.spaces.interaction.public import EvaluationMaterial
from pydantic import Field, JsonValue

type Judgement = Literal["met", "not_met", "unknown"]
type Qualification = Literal["eligible", "ineligible", "unknown"]
type Verdict = Literal["positive", "negative"]
type Wording = Annotated[str, Field(min_length=1, max_length=768)]
type Index = Annotated[int, Field(ge=1)]
type HistoryKey = tuple[UUID, int, UUID, int, str]


class QuotedSource(FactModel):
    material: Index
    quote: Wording


class ExecutionCheck(FactModel):
    criterion_id: UUID
    judgement: Judgement
    sources: list[QuotedSource]
    reason: Wording


class Candidate(FactModel):
    choice: Index
    execution_checks: list[ExecutionCheck]
    aspect_judgement: Judgement
    source_spans: list[QuotedSource]
    method_source: QuotedSource | None = None
    reason: Wording
    limitations: list[Wording]


class Unattributed(FactModel):
    source_spans: list[QuotedSource]
    reason: Wording


class TestedScope(FactModel):
    item_id: UUID
    source: QuotedSource


class Interpretation(FactModel):
    candidates: list[Candidate]
    unattributed: list[Unattributed]
    declared_external_help: QuotedSource | None
    covered_scopes: list[TestedScope] = Field(default_factory=list[TestedScope])


class EvidenceSpan(FactModel):
    ref: EventPartRef
    quote: str


class ConditionFact(FactModel):
    condition: str
    status: Literal["known", "unknown", "not_applicable"]
    value: JsonValue
    source_refs: list[EventPartRef]


class CheckedEvidence(FactModel):
    claim_ref: ClaimRef
    method_ref: SolutionRef
    aspect_code: str
    rule_ref: Ref
    execution_checks: list[ExecutionCheck]
    condition_facts: list[ConditionFact]
    source_spans: list[EvidenceSpan]
    qualification: Qualification
    verdict: Verdict | None
    reason_codes: list[str]
    reason: str
    limitations: list[str]


@dataclass(frozen=True)
class Choice:
    claim: ClaimRef
    method: SolutionRef
    aspect: str
    criterion_ids: tuple[UUID, ...]
    definition: dict[str, JsonValue]


def choices(bundle: EvaluationMaterials) -> list[Choice]:
    """模型只能选择程序由固定引用产生的分项编号。"""
    definitions = {claim.claim_ref: claim.definition for claim in bundle.claims}
    options: list[Choice] = []
    for candidate in bundle.record.input.candidate_scope:
        definition = definitions[candidate.claim_ref]
        criteria = {criterion.criterion_id: criterion for criterion in definition.criteria}
        allowed = {
            (item.method_ref.object_id, item.method_ref.version) for item in candidate.methods
        }
        for method in definition.methods:
            # 只保留本次候选范围内允许的解法。
            if (method.method_ref.object_id, method.method_ref.version) not in allowed:
                continue
            for rule in method.aspect_rules:
                # 非标准方面规则不纳入模型可选分项。
                if rule.aspect_code not in STANDARD_ASPECTS:
                    continue
                options.append(
                    Choice(
                        candidate.claim_ref,
                        method.method_ref,
                        rule.aspect_code,
                        tuple(method.criterion_ids),
                        {
                            "task_title": definition.title,
                            "method": method.method_ref.model_dump(mode="json"),
                            "rule": rule.model_dump(mode="json"),
                            "criteria": [
                                criteria[identity].model_dump(mode="json")
                                for identity in method.criterion_ids
                            ],
                        },
                    )
                )
    return options


def prompt(
    bundle: EvaluationMaterials,
    historical: dict[HistoryKey, ConditionFact] | None = None,
    comparisons: list[EvaluationMaterial] | None = None,
) -> str:
    """按固定候选编号装载原文及判据，输入不包含已有概率。"""
    return canonical_json(
        {
            "source_kind": bundle.source.source_kind,
            "materials": [item.model_dump(mode="json") for item in bundle.source.materials],
            "choices": [
                {
                    **item.definition,
                    # 命中历史条件则带上，否则留空。
                    "historical_condition": fact.model_dump(mode="json")
                    if (fact := (historical or {}).get(_history_key(item)))
                    else None,
                }
                for item in choices(bundle)
            ],
            "comparison_questions": [item.model_dump(mode="json") for item in (comparisons or [])],
            "domain_facts": [
                {"ref": ref.model_dump(mode="json"), "body": body}
                for ref, body in bundle.domain.items()
            ],
            "target_scopes": [
                {
                    "item_id": str(item.item_id),
                    "claim_id": str(item.claim_ref.claim_id),
                    "scope": item.task_conditions.description,
                }
                for item in bundle.targets
                # 仅纳入带范围描述的目标项。
                if item.task_conditions.description
            ],
            "missing_reasons": bundle.record.input.missing_reasons,
        }
    )


def _contains(value: JsonValue, quote: str) -> bool:
    # 字符串直接判包含；列表与字典递归下钻；其余类型不参与匹配。
    if isinstance(value, str):
        return quote in value
    if isinstance(value, list):
        return any(_contains(item, quote) for item in value)
    if isinstance(value, dict):
        return any(_contains(item, quote) for item in value.values())
    return False


def _span(
    materials: list[EvaluationMaterial], quoted: QuotedSource, source_kind: str
) -> EvidenceSpan:
    # 材料编号超出固定清单范围，判引用越界。
    if quoted.material > len(materials):
        raise ValueError("Evaluation citation is outside the fixed material list")
    material = materials[quoted.material - 1]
    expected = "answer" if source_kind == "answer" else "teaching"
    content = material.content
    if isinstance(content, dict):
        # 优先取正文文本；教学材料再退回到 content 字段。
        content = content.get("text") or (
            content.get("content") if expected == "teaching" else None
        )
    # 角色不符、引文为空或原文中检索不到该引文，均判引文归属不成立。
    if (
        material.role != expected
        or not quoted.quote.strip()
        or not _contains(content, quoted.quote)
    ):
        raise ValueError("Cited words do not occur in the student or provided teaching text")
    return EvidenceSpan(ref=material.ref, quote=quoted.quote)


def _independence(bundle: EvaluationMaterials, external_help: bool) -> str | None:
    material = _help_material(bundle)
    basis = material.content if material else None
    # 缺少帮助历史记录，无法判断独立性。
    if not isinstance(basis, dict) or basis.get("help_event_ids") is None:
        return "help_history_unknown"
    # 非检测模式或无轮次引用，本轮不构成独立作答场景。
    if basis.get("mode") != "detection" or bundle.source.round_ref is None:
        return "not_an_independent_round"
    # 轮次事实本身缺失，独立性无法核验。
    if "round_facts_missing" in bundle.source.missing_reasons:
        return "round_facts_missing"
    # 模型声明了外部帮助，或记录显示已使用外部帮助。
    if external_help or basis.get("external_help") == "used":
        return "declared_external_help"
    # 材料中存在被提供的实质性帮助，判为受助作答。
    if any(
        item.role == "help"
        and isinstance(item.content, dict)
        and item.content.get("stage") == "provided"
        and item.content.get("classification") == "substantive"
        for item in bundle.source.materials
    ):
        return "substantive_help"
    # 既往任务使用记录缺失，暴露情况未知。
    if basis.get("prior_task_use_event_ids") is None:
        return "prior_exposure_unknown"
    # 既往使用记录非空，说明此前接触过该任务。
    if basis.get("prior_task_use_event_ids"):
        return "previously_exposed"
    return None


def _history_key(choice: Choice) -> HistoryKey:
    return (
        choice.claim.claim_id,
        choice.claim.revision,
        choice.method.object_id,
        choice.method.version,
        choice.aspect,
    )


def check(
    bundle: EvaluationMaterials,
    interpretation: Interpretation,
    historical: dict[HistoryKey, ConditionFact] | None = None,
) -> list[CheckedEvidence]:
    """只接收有原文和固定规则依据的分项，冲突合并为未决。"""
    options = choices(bundle)
    materials = bundle.source.materials
    kind = bundle.source.source_kind
    # 仅作答类需要核对题干范围覆盖。
    question_scopes = _question_scopes(bundle, interpretation) if kind == "answer" else {}
    external_help = (
        _span(materials, interpretation.declared_external_help, "answer")
        if interpretation.declared_external_help
        else None
    )
    # 先校验未归属片段的引文均可在固定材料中定位。
    for item in interpretation.unattributed:
        for quote in item.source_spans:
            _span(materials, quote, kind)
    methods: dict[tuple[UUID, str, str], set[UUID]] = {}
    # 首轮遍历统计同一引文被哪些解法引用，供后续判定方法是否未归属。
    for candidate in interpretation.candidates:
        if candidate.choice > len(options):
            raise ValueError("Evaluation candidate is outside the adopted scope")
        if candidate.method_source is None:
            continue
        choice = options[candidate.choice - 1]
        source = _span(materials, candidate.method_source, kind)
        identity = (choice.claim.claim_id, str(source.ref.event_id), source.quote)
        methods.setdefault(identity, set()).add(choice.method.object_id)
    results: dict[int, CheckedEvidence] = {}
    for candidate in interpretation.candidates:
        if candidate.choice > len(options):
            raise ValueError("Evaluation candidate is outside the adopted scope")
        choice = options[candidate.choice - 1]
        fragment = [_span(materials, quote, kind) for quote in candidate.source_spans]
        signature = (
            _span(materials, candidate.method_source, kind) if candidate.method_source else None
        )
        checks = candidate.execution_checks
        for criterion in checks:
            # 判据必须属于当前解法，不得跨解法套用。
            if criterion.criterion_id not in choice.criterion_ids:
                raise ValueError("Evaluation candidate used a criterion from another method")
            for quote in criterion.sources:
                _span(materials, quote, kind)
            # 给出明确判定结论时必须附带来源引文。
            if criterion.judgement != "unknown" and not criterion.sources:
                raise ValueError("An explicit criterion judgement requires a source")
        verified = (historical or {}).get(_history_key(choice))
        qualification, reason = _qualification(
            bundle, interpretation, candidate, choice, fragment, verified
        )
        # 合格但解法缺少归属依据，或同一引文被多个解法共用，降级为未归属。
        if qualification == "eligible" and (
            signature is None
            or len(methods[choice.claim.claim_id, str(signature.ref.event_id), signature.quote]) > 1
        ):
            qualification, reason = "unknown", "method_unattributed"
        verdict: Verdict | None = None
        # 仅合格的作答记录才由方面结论映射正/反证。
        if qualification == "eligible" and kind == "answer":
            verdict = "positive" if candidate.aspect_judgement == "met" else "negative"
        entry = CheckedEvidence(
            claim_ref=choice.claim,
            method_ref=choice.method,
            aspect_code=choice.aspect,
            rule_ref=Ref(
                owner="evaluation",
                type="aspect_rule",
                id=f"{choice.claim.claim_id}:{choice.method.object_id}:{choice.aspect}",
                revision=choice.claim.revision,
            ),
            execution_checks=checks,
            condition_facts=[
                *_help_conditions(bundle, external_help),
                *question_scopes.get(choice.claim.claim_id, []),
                *([verified] if verified else []),
            ],
            source_spans=list(dict.fromkeys([*fragment, *([signature] if signature else [])])),
            qualification=qualification,
            verdict=verdict,
            reason_codes=[reason],
            reason=candidate.reason,
            limitations=candidate.limitations,
        )
        previous = results.get(candidate.choice)
        # 同一候选出现多次时合并记录，冲突由合并逻辑降级。
        if previous is not None:
            entry = _merge(previous, entry)
        results[candidate.choice] = entry
    return list(results.values())


def _question_scopes(
    bundle: EvaluationMaterials, interpreted: Interpretation
) -> dict[UUID, list[ConditionFact]]:
    targets = {item.item_id: item for item in bundle.targets}
    conditions: dict[UUID, list[ConditionFact]] = {}
    seen: set[UUID] = set()
    for check in interpreted.covered_scopes:
        target = targets.get(check.item_id)
        # 目标项不在冻结采用范围内，或重复登记，均判越界。
        if not target or check.item_id in seen:
            raise ValueError("Target scope is outside the frozen adoption or duplicated")
        seen.add(check.item_id)
        if check.source.material > len(bundle.source.materials):
            continue
        question = bundle.source.materials[check.source.material - 1]
        # 角色不符或引文检索不到，保留已独立核验的表现，不写入范围条件。
        if question.role != "question" or not _contains(question.content, check.source.quote):
            continue
        conditions.setdefault(target.claim_ref.claim_id, []).append(
            ConditionFact(
                condition="target_scope",
                status="known",
                value=target.task_conditions.description,
                source_refs=[question.ref],
            )
        )
    return conditions


def _help_material(bundle: EvaluationMaterials) -> EvaluationMaterial | None:
    return next((item for item in bundle.source.materials if item.role == "help_basis"), None)


def _help_conditions(
    bundle: EvaluationMaterials, declaration: EvidenceSpan | None
) -> list[ConditionFact]:
    basis = _help_material(bundle)
    # 无帮助依据材料时不产出帮助条件。
    if basis is None:
        return []
    if declaration is None:
        # 模型未单独声明：以记录中的外部帮助标记为准，非明确取值则置空。
        reported = basis.content.get("external_help") if isinstance(basis.content, dict) else None
        external = reported if reported in ("used", "declared_none") else None
        external_refs = [basis.ref]
    else:
        # 模型已声明外部帮助，直接记为已使用并指向该声明片段。
        external, external_refs = "used", [declaration.ref]
    known = isinstance(basis.content, dict) and basis.content.get("help_event_ids") is not None
    return [
        ConditionFact(
            condition="external_help",
            status="unknown" if external is None else "known",
            value=external,
            source_refs=external_refs,
        ),
        ConditionFact(
            condition="system_help_history_complete",
            status="known",
            value=known,
            source_refs=[basis.ref],
        ),
    ]


def _qualification(
    bundle: EvaluationMaterials,
    interpretation: Interpretation,
    candidate: Candidate,
    choice: Choice,
    spans: list[EvidenceSpan],
    verified: ConditionFact | None,
) -> tuple[Qualification, str]:
    # 方面结论未知或无有效片段，表现依据不足。
    if candidate.aspect_judgement == "unknown" or not spans:
        return "unknown", "insufficient_performance"
    if bundle.source.source_kind == "teaching":
        # 教学场景只评估独立与理解两类方面。
        if choice.aspect not in {"independent", "understanding"}:
            return "ineligible", "no_learning_transfer_for_aspect"
        # 教学结论未达成，判教学记录不合格。
        if candidate.aspect_judgement != "met":
            return "ineligible", "teaching_incomplete"
        return "eligible", "qualified_teaching"
    # 作答场景缺原题，无法核对范围。
    if not any(item.role == "question" for item in bundle.source.materials):
        return "unknown", "original_question_missing"
    # 任务实例的领域事实未取到，固定引用缺失。
    if bundle.source.task_instance_ref not in bundle.domain:
        return "unknown", "fixed_reference_missing"
    if choice.aspect in {"independent", "transfer", "retention"}:
        issue = _independence(bundle, interpretation.declared_external_help is not None)
        # 信息缺失类问题记未知，待补证。
        if issue in {"help_history_unknown", "round_facts_missing", "prior_exposure_unknown"}:
            return "unknown", issue
        # 其余独立性问题判不合格。
        if issue:
            return "ineligible", issue
        passed = {
            item.criterion_id for item in candidate.execution_checks if item.judgement == "met"
        }
        # 方面判定达成但判据未全部通过，判执行核对不足。
        if candidate.aspect_judgement == "met" and not set(choice.criterion_ids) <= passed:
            return "unknown", "execution_checks_missing"
    # 迁移方面缺历史基线，无法判定。
    if choice.aspect == "transfer" and verified is None:
        return "unknown", "transfer_basis_unknown"
    if choice.aspect == "retention":
        # 保持方面缺历史基线或基线非结构化记录，无法判定。
        if verified is None or not isinstance(verified.value, dict):
            return "unknown", "retention_basis_unknown"
        # 保持期未达到下限，判不合格。
        if verified.value.get("minimum_met") is not True:
            return "ineligible", "retention_interval_too_short"
    return "eligible", "qualified_observation"


def _merge(previous: CheckedEvidence, incoming: CheckedEvidence) -> CheckedEvidence:
    # 先比对资格与正反证结论是否一致。
    same = (previous.qualification, previous.verdict) == (incoming.qualification, incoming.verdict)
    by_criterion = {item.criterion_id: item.judgement for item in previous.execution_checks}
    # 再比对同一判据上的结论是否相互冲突。
    conflict = any(
        item.criterion_id in by_criterion and item.judgement != by_criterion[item.criterion_id]
        for item in incoming.execution_checks
    )
    # 结论一致且无判据冲突才可保留既有判定，否则整体降级未决。
    compatible = same and not conflict
    return previous.model_copy(
        update={
            "source_spans": list(dict.fromkeys([*previous.source_spans, *incoming.source_spans])),
            "qualification": previous.qualification if compatible else "unknown",
            "verdict": previous.verdict if compatible else None,
            "reason_codes": previous.reason_codes if compatible else ["conflicting_candidate"],
        }
    )
