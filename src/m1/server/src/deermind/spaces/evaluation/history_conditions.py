"""Verify historical conditions from the bounded sources of this assessment."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.product.public.learning_targets import GoalItem
from deermind.spaces.domain.public import SolutionRef
from deermind.spaces.evaluation.goal_calculation import THRESHOLD
from deermind.spaces.evaluation.inputs import EvaluationMaterials, ReadPriorQuestions, ReadSource
from deermind.spaces.evaluation.interpretation import ConditionFact
from deermind.spaces.evaluation.public import ClaimRef
from deermind.spaces.interaction.public import EvaluationMaterial
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

MINIMUM_RETENTION = timedelta(days=7)
MAX_HISTORY = 100
type Key = tuple[UUID, int, UUID, int, str]


@dataclass(frozen=True)
class History:
    checks: dict[Key, ConditionFact]
    comparison: tuple[EvaluationMaterial, ...] = ()


def _known(name: str, value: JsonValue, *sources: EventPartRef) -> ConditionFact:
    return ConditionFact(condition=name, status="known", value=value, source_refs=list(sources))


def _identifies(target: GoalItem, claim: ClaimRef, method: SolutionRef) -> bool:
    return target.claim_ref == claim and any(item.method_ref == method for item in target.methods)


def _times(question: EvaluationMaterial, bundle: EvaluationMaterials) -> datetime | None:
    # 内容不是字典时取不到准备时间。
    raw = question.content.get("prepared_at") if isinstance(question.content, dict) else None
    if not isinstance(raw, str):
        return None
    try:
        start = datetime.fromisoformat(raw)
    except ValueError:
        # 时间串无法按 ISO 格式解析。
        return None
    # 时间须带时区，且不能晚于本次作答发生时间。
    if start.utcoffset() is None or start > bundle.source.occurred_at:
        return None
    return start.astimezone(UTC)


def _table(material: EvaluationMaterial) -> bool:
    sentence = material.content.get("statement") if isinstance(material.content, dict) else None
    if not isinstance(sentence, dict):
        return False
    # 题干声明中挂有数据表即视为表格题。
    return bool(sentence.get("data_tables"))


async def collect(
    db: AsyncConnection,
    bundle: EvaluationMaterials,
    read_source: ReadSource,
    read_prior: ReadPriorQuestions | None,
) -> History:
    question = next((item for item in bundle.source.materials if item.role == "question"), None)
    # 缺题干或无轮次引用，无法回溯历史，直接返回空结论。
    if question is None or bundle.source.round_ref is None:
        return History({})
    start = _times(question, bundle)
    # 准备时间缺失或非法，同样不做历史条件判定。
    if start is None:
        return History({})
    rows = (
        await db.execute(
            text("""
        SELECT p.trigger_event_id,p.source_seq,p.input,e.claim_id,e.claim_revision,e.method_id,
            e.method_version,e.aspect_code,e.verdict,e.source_kind,r.p_obs_after,
            r.last_observed_at,e.source_spans
        FROM evaluation.evidence e JOIN evaluation.evaluation_input p ON p.input_id=e.input_ref
        LEFT JOIN evaluation.belief_revision r ON r.evidence_ref=e.evidence_id
        WHERE e.scope_id=:scope AND p.source_seq<:seq AND e.qualification='eligible'
        ORDER BY p.source_seq, e.evidence_id LIMIT :limit
    """),
            {
                "scope": bundle.source.scope_id,
                "seq": bundle.source.source_seq,
                "limit": MAX_HISTORY + 1,
            },
        )
    ).all()
    # 历史记录超出上限，避免大范围回溯，直接放弃历史条件判定。
    if len(rows) > MAX_HISTORY:
        return History({})
    checks: dict[Key, ConditionFact] = {}
    comparisons: dict[UUID, EvaluationMaterial] = {}
    known_basis = bundle.record.input.target_basis_ref.id
    # 逐个候选主张 × 解法核对，仅保留与本次目标项对得上的组合。
    for candidate in bundle.record.input.candidate_scope:
        claim = candidate.claim_ref
        for method in candidate.methods:
            reference = method.method_ref
            # 该主张与解法未出现在任何目标项上，跳过。
            if not any(_identifies(target, claim, reference) for target in bundle.targets):
                continue
            key = (claim.claim_id, claim.revision, reference.object_id, reference.version)
            history = [
                row
                for row in rows
                if (row.claim_id, row.claim_revision, row.method_id, row.method_version) == key
            ]
            by_aspect: dict[str, Decimal] = {}
            anchor = None
            earlier_success = None
            for row in history:
                # 只认作答类、早于本次准备时间、且观测概率有效的记录。
                if not (
                    row.source_kind == "answer"
                    and row.last_observed_at is not None
                    and row.last_observed_at < start
                    and row.p_obs_after is not None
                ):
                    continue
                # 记录此前在独立判断方面获得正证的那条，供迁移题型判定使用。
                if row.aspect_code == "independent" and row.verdict == "positive":
                    earlier_success = row
                # 依据基准与本次不一致的记录不计入后续锚点统计。
                if row.input["target_basis_ref"]["id"] != known_basis:
                    continue
                by_aspect[row.aspect_code] = Decimal(str(row.p_obs_after))
                # 首次出现两方面概率均达阈值的记录，作为保持期锚点。
                if anchor is None and all(
                    by_aspect.get(aspect, Decimal(0)) >= THRESHOLD
                    for aspect in ("independent", "understanding")
                ):
                    anchor = row
            # 锚点可定位到原文片段时，计算距本次准备的保持期与相关练习。
            if anchor and anchor.source_spans:
                chosen = EventPartRef.model_validate_json(
                    canonical_json(anchor.source_spans[0]["ref"])
                )
                anchor_at: datetime = anchor.last_observed_at
                elapsed = start - anchor_at
                practiced: list[JsonValue] = [
                    str(event)
                    for event in dict.fromkeys(
                        row.trigger_event_id
                        for row in history
                        if row.source_seq > anchor.source_seq
                        and row.trigger_event_id != anchor.trigger_event_id
                    )
                ]
                details: dict[str, JsonValue] = {
                    "minimum_met": elapsed >= MINIMUM_RETENTION,
                    "anchor_at": anchor_at.isoformat(),
                    "opened_at": start.isoformat(),
                    "submitted_at": bundle.source.occurred_at.isoformat(),
                    "elapsed_seconds": elapsed.total_seconds(),
                    "related_practice": practiced,
                }
                checks[(*key, "retention")] = _known(
                    "retention_window",
                    details,
                    chosen,
                    question.ref,
                )
            # 本次为表格题、且存在此前正证时，才判断是否发生文字到表格的题型迁移。
            if earlier_success and _table(question) and read_prior is not None:
                previous_questions = await read_prior(
                    bundle.source.scope_id, bundle.source.source_seq, candidate.task_ref, reference
                )
                # 取不到历史题，或历史上还出现过其他表格题，不构成纯迁移对照。
                if previous_questions is None or any(
                    _table(item) and item.ref != question.ref for item in previous_questions
                ):
                    continue
                prior = await read_source(bundle.source.scope_id, earlier_success.trigger_event_id)
                comparison = next(
                    (item for item in prior.materials if item.role == "question"), None
                )
                # 此前题干为非表格的文字题，记为文字转表格迁移。
                if comparison and not _table(comparison):
                    comparisons[comparison.ref.event_id] = comparison
                    checks[(*key, "transfer")] = _known(
                        "transfer_type", "text_to_table", comparison.ref, question.ref
                    )
    return History(checks, tuple(comparisons.values()))
