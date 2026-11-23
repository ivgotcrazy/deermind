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
    raw = question.content.get("prepared_at") if isinstance(question.content, dict) else None
    if not isinstance(raw, str):
        return None
    try:
        start = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if start.utcoffset() is None or start > bundle.source.occurred_at:
        return None
    return start.astimezone(UTC)


def _table(material: EvaluationMaterial) -> bool:
    sentence = material.content.get("statement") if isinstance(material.content, dict) else None
    if not isinstance(sentence, dict):
        return False
    return bool(sentence.get("data_tables"))


async def collect(
    db: AsyncConnection,
    bundle: EvaluationMaterials,
    read_source: ReadSource,
    read_prior: ReadPriorQuestions | None,
) -> History:
    question = next((item for item in bundle.source.materials if item.role == "question"), None)
    if question is None or bundle.source.round_ref is None:
        return History({})
    start = _times(question, bundle)
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
    if len(rows) > MAX_HISTORY:
        return History({})
    checks: dict[Key, ConditionFact] = {}
    comparisons: dict[UUID, EvaluationMaterial] = {}
    known_basis = bundle.record.input.target_basis_ref.id
    for candidate in bundle.record.input.candidate_scope:
        claim = candidate.claim_ref
        for method in candidate.methods:
            reference = method.method_ref
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
                if not (
                    row.source_kind == "answer"
                    and row.last_observed_at is not None
                    and row.last_observed_at < start
                    and row.p_obs_after is not None
                ):
                    continue
                if row.aspect_code == "independent" and row.verdict == "positive":
                    earlier_success = row
                if row.input["target_basis_ref"]["id"] != known_basis:
                    continue
                by_aspect[row.aspect_code] = Decimal(str(row.p_obs_after))
                if anchor is None and all(
                    by_aspect.get(aspect, Decimal(0)) >= THRESHOLD
                    for aspect in ("independent", "understanding")
                ):
                    anchor = row
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
            if earlier_success and _table(question) and read_prior is not None:
                previous_questions = await read_prior(
                    bundle.source.scope_id, bundle.source.source_seq, candidate.task_ref, reference
                )
                if previous_questions is None or any(
                    _table(item) and item.ref != question.ref for item in previous_questions
                ):
                    continue
                prior = await read_source(bundle.source.scope_id, earlier_success.trigger_event_id)
                comparison = next(
                    (item for item in prior.materials if item.role == "question"), None
                )
                if comparison and not _table(comparison):
                    comparisons[comparison.ref.event_id] = comparison
                    checks[(*key, "transfer")] = _known(
                        "transfer_type", "text_to_table", comparison.ref, question.ref
                    )
    return History(checks, tuple(comparisons.values()))
