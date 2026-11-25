"""Turn checked evidence into one atomic mastery result."""

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid4, uuid5

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, ProducerAccess, Ref
from deermind.abstractions.executions import RunInput
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.executions import commands, store
from deermind.foundation.system.executions.contracts import Registry
from deermind.foundation.system.waits.results import Results
from deermind.spaces.evaluation import belief, interpretation, interpretation_facts
from deermind.spaces.evaluation import mastery_facts as facts
from deermind.spaces.evaluation import sequence as ordering
from deermind.spaces.evaluation.input_facts import InputRecord
from deermind.spaces.evaluation.inputs import ACTOR, EvaluationInputs
from deermind.spaces.evaluation.publication import POLICY, result_key
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

type Key = tuple[UUID, int, UUID, int, str]


def _key(value: facts.Subitem) -> Key:
    return (
        value.claim_id,
        value.claim_revision,
        value.method_id,
        value.method_version,
        value.aspect_code,
    )


def evidence_record(
    source: InputRecord,
    interpretation_id: UUID,
    checked: interpretation.CheckedEvidence,
    now: datetime,
) -> facts.EvidenceRecord:
    claim, method = checked.claim_ref, checked.method_ref
    identity = uuid5(
        source.source_id,
        f"{source.scope_id}:{source.source_kind}:{claim.claim_id}:{claim.revision}:"
        f"{method.object_id}:{method.version}:{checked.aspect_code}",
    )
    references = [span.ref for span in checked.source_spans]
    for condition in checked.condition_facts:
        references.extend(condition.source_refs)
    return facts.EvidenceRecord(
        evidence_id=identity,
        input_ref=source.input_id,
        interpretation_ref=interpretation_id,
        scope_id=source.scope_id,
        claim_id=claim.claim_id,
        claim_revision=claim.revision,
        method_id=method.object_id,
        method_version=method.version,
        aspect_code=cast(facts.Aspect, checked.aspect_code),
        source_kind=source.source_kind,
        source_id=source.source_id,
        execution_checks=checked.execution_checks,
        rule_ref=checked.rule_ref,
        condition_facts=checked.condition_facts,
        source_spans=checked.source_spans,
        source_refs=list(dict.fromkeys(references)),
        qualification=checked.qualification,
        verdict=checked.verdict,
        reason_codes=checked.reason_codes,
        reason=checked.reason,
        limitations=checked.limitations,
        created_at=now,
    )


def calculate_revision(
    item: facts.EvidenceRecord,
    previous: facts.MasteryItem | None,
    source: InputRecord,
) -> facts.BeliefRevision | None:
    # 佐证不合格则不产生信念修订。
    if item.qualification != "eligible":
        return None
    parameters = belief.M1_PARAMETERS
    prior = previous.p_current if previous else parameters.p0
    observed = previous.p_obs if previous else None
    last_seen = previous.last_observed_at if previous else None
    kind: Literal["observation", "learning_transition"]
    # 有判定结论走观测更新；无结论只做学习状态推演。
    if item.verdict:
        kind = "observation"
        posterior = belief.update_observation(prior, item.verdict, parameters)
        next_observed, next_current = posterior.p_obs, posterior.p_current
        last_seen = source.input.occurred_at
    else:
        kind = "learning_transition"
        next_observed = observed
        next_current = belief.predict_learning(prior, item.aspect_code, True, parameters)
        # 推演后当前概率未变化，不记修订。
        if next_current == prior:
            return None
    return facts.BeliefRevision(
        belief_revision_id=uuid5(item.evidence_id, kind),
        scope_id=item.scope_id,
        claim_id=item.claim_id,
        claim_revision=item.claim_revision,
        method_id=item.method_id,
        method_version=item.method_version,
        aspect_code=item.aspect_code,
        previous_revision_id=UUID(previous.belief_revision_ref.id)
        if previous and previous.belief_revision_ref
        else None,
        evidence_ref=item.evidence_id,
        update_kind=kind,
        p_obs_before=observed,
        p_current_before=prior,
        p_obs_after=next_observed,
        p_current_after=next_current,
        last_observed_at=last_seen,
        parameter_ref=source.input.parameter_ref,
        algorithm_ref=source.input.algorithm_ref,
        reason_codes=item.reason_codes,
        trigger_event_id=source.trigger_event_id,
        created_at=item.created_at,
    )


def projected_item(
    item: facts.EvidenceRecord,
    previous: facts.MasteryItem | None,
    change: facts.BeliefRevision | None,
) -> facts.MasteryItem:
    seen = change.last_observed_at if change else previous.last_observed_at if previous else None
    return facts.MasteryItem(
        scope_id=item.scope_id,
        claim_id=item.claim_id,
        claim_revision=item.claim_revision,
        method_id=item.method_id,
        method_version=item.method_version,
        aspect_code=item.aspect_code,
        p_obs=change.p_obs_after if change else previous.p_obs if previous else None,
        p_current=change.p_current_after
        if change
        else previous.p_current
        if previous
        else belief.M1_PARAMETERS.p0,
        last_observed_at=seen,
        belief_revision_ref=facts.ref("belief_revision", change.belief_revision_id)
        if change
        else previous.belief_revision_ref
        if previous
        else None,
        observation_status="observed" if seen else "unknown",
        evidence_coverage=[facts.ref("evidence", item.evidence_id)]
        if item.verdict
        else previous.evidence_coverage
        if previous
        else [],
        unknown_reasons=item.reason_codes if item.qualification == "unknown" else [],
        source_refs=item.source_refs,
    )


async def _latest(db: AsyncConnection, scope: UUID) -> facts.MasterySnapshot | None:
    row = await db.scalar(
        text("""
        SELECT to_jsonb(s)-'source_event_id'
        FROM evaluation.mastery_head h
        JOIN evaluation.mastery_snapshot s ON s.snapshot_id=h.current_snapshot_ref
        WHERE h.scope_id=:scope
    """),
        {"scope": scope},
    )
    return facts.MasterySnapshot.model_validate_json(canonical_json(row)) if row else None


class Mastery:
    def __init__(self, inputs: EvaluationInputs, registry: Registry) -> None:
        self.inputs, self.registry = inputs, registry
        self.results = Results(registry, [POLICY])

    async def save(self, run: RunInput, reference: Ref) -> Ref:
        expected = facts.ref("mastery_snapshot", uuid5(run.execution_id, "mastery"))
        async with self.inputs.engine.connect() as db:
            work = await store.load(db, run.execution_id)
            source, checked = await self._records(db, work.scope_id, reference)
            prior = await _latest(db, work.scope_id)
            # 已完成且仍是本次尝试：幂等重入，核对快照引用后直接返回。
            if work.state == "completed" and work.active_attempt_id == run.attempt_id:
                if work.result_ref != expected:
                    raise ValueError("Evaluation has a different saved batch")
                return expected
            body = await self._result(db, run, source, checked, prior)
        scope = ("learning_space", source.scope_id)
        trigger = source.trigger_event_id
        access = ProducerAccess("evaluation", ACTOR, frozenset({scope}), frozenset({trigger}))
        draft = EventDraft(
            uuid4(),
            facts.COMPLETED,
            1,
            *scope,
            body.result_ref,
            body.model_dump(mode="json"),
            None,
            causation_event_id=trigger,
            source_execution_ref=run.execution_id,
        )
        prepared = await self.inputs.attachments.prepare(self.inputs.events, access, (draft,))
        async with self.inputs.engine.begin() as db:
            current = await store.lock_owned(db, self.registry, run.execution_id)
            # 加锁后再次确认已完成且为本次尝试，避免并发重复落库。
            if current.state == "completed" and current.active_attempt_id == run.attempt_id:
                if current.result_ref != body.result_ref:
                    raise ValueError("Evaluation has a different saved batch")
                return body.result_ref
            await store.active(db, self.registry, run, "finish")
            # 执行输入引用须与本次触发一致，防止结果挂错执行。
            if current.input_ref.id != str(trigger):
                raise ValueError("Evaluation result does not belong to this execution")
            await ordering.protect(db, source.scope_id, trigger)
            sequence = await lock_scope_sequence(db, *scope)
            latest = await _latest(db, source.scope_id)
            # 提交前复核：头快照与计算时读到的基线不一致，说明状态已被改动，中止本次落库。
            if (latest.snapshot_id if latest else None) != (prior.snapshot_id if prior else None):
                raise RuntimeError("Evaluation state changed before commit")
            (event,) = await self.inputs.events.append(
                db,
                access,
                prepared,
                commit_id=uuid4(),
                correlation_id=trigger,
                expected_seq={scope: sequence},
            )
            await facts.project(db, event)
            key = result_key(source.scope_id, trigger)
            await self.results.expect(db, run, key)
            await self.results.publish(
                db,
                run,
                key,
                result_ref=body.result_ref,
                event_id=event.draft.event_id,
                payload={"status": "updated" if body.belief_revision_refs else "unchanged"},
                publication_refs=[body.snapshot_ref],
            )
            await ordering.finish(db, source.scope_id)
            await commands.complete(db, self.registry, run, body.result_ref)
        return body.result_ref

    @staticmethod
    async def _records(
        db: AsyncConnection, scope: UUID, reference: Ref
    ) -> tuple[InputRecord, interpretation_facts.InterpretationRecord | None]:
        # 批次只能挂在已准备的输入或其解释记录之下。
        if reference.owner != "evaluation" or reference.type not in {
            "evaluation_input",
            "interpretation",
        }:
            raise ValueError("Evaluation batch requires a prepared input or interpretation")
        identity = UUID(reference.id)
        interpretation_row = None
        # 引用指向解释时先回读解释记录，并取其所属输入作为定位基准。
        if reference.type == "interpretation":
            raw = await db.scalar(
                text("""
                SELECT to_jsonb(i)-'source_event_id'
                FROM evaluation.interpretation i
                JOIN evaluation.evaluation_input p ON p.input_id=i.input_ref
                WHERE i.interpretation_id=:id AND p.scope_id=:scope
            """),
                {"id": identity, "scope": scope},
            )
            interpretation_row = interpretation_facts.InterpretationRecord.model_validate_json(
                canonical_json(raw)
            )
            identity = interpretation_row.input_ref
        raw = await db.scalar(
            text("""
            SELECT to_jsonb(p)-'source_event_id' FROM evaluation.evaluation_input p
            WHERE p.input_id=:id AND p.scope_id=:scope
        """),
            {"id": identity, "scope": scope},
        )
        source = InputRecord.model_validate_json(canonical_json(raw))
        # 输入钉住的参数与算法引用须为当前认可的 BKT 公式版本。
        if (source.input.parameter_ref, source.input.algorithm_ref) != (
            belief.PARAMETER_REF,
            belief.ALGORITHM_REF,
        ):
            raise ValueError("Unrecognized pinned belief formula")
        return source, interpretation_row

    @staticmethod
    async def _result(
        db: AsyncConnection,
        run: RunInput,
        source: InputRecord,
        checked: interpretation_facts.InterpretationRecord | None,
        prior: facts.MasterySnapshot | None,
    ) -> facts.BeliefCompleted:
        identity = uuid5(run.execution_id, "mastery")
        now = datetime.now(UTC)
        items = {_key(item): item for item in prior.items} if prior else {}
        evidence: list[facts.EvidenceRecord] = []
        changes: list[facts.BeliefRevision] = []
        reasons: set[str] = set()
        if checked:
            for value in checked.validation:
                entry = evidence_record(source, checked.interpretation_id, value, now)
                # 佐证已落库则记重复来源，跳过本条不重复计算。
                if await db.scalar(
                    text("SELECT 1 FROM evaluation.evidence WHERE evidence_id=:id"),
                    {"id": entry.evidence_id},
                ):
                    reasons.add("duplicate_source")
                    continue
                key = _key(entry)
                change = calculate_revision(entry, items.get(key), source)
                evidence.append(entry)
                items[key] = projected_item(entry, items.get(key), change)
                reasons.update(entry.reason_codes)
                if change:
                    changes.append(change)
                # 合格但未产生数值变化，单独记录原因。
                elif entry.qualification == "eligible":
                    reasons.add("no_numeric_change")
        # 既无佐证也无任何原因码时，兜底记为无可归属证据。
        if not evidence and not reasons:
            reasons.add("no_attributable_evidence")
        snapshot = facts.MasterySnapshot(
            snapshot_id=identity,
            scope_id=source.scope_id,
            publication_seq=1 if prior is None else prior.publication_seq + 1,
            items=list(items.values()),
            coverage=[
                facts.Subitem.model_validate(item, from_attributes=True) for item in items.values()
            ],
            result_coverage=[
                Ref(owner="interaction", type="event", id=str(source.trigger_event_id))
            ],
            published_at=now,
        )
        reference = facts.ref("mastery_snapshot", identity)
        return facts.BeliefCompleted(
            trigger_event_id=source.trigger_event_id,
            input_ref=facts.ref("evaluation_input", source.input_id),
            evidence_refs=[facts.ref("evidence", item.evidence_id) for item in evidence],
            belief_revision_refs=[
                facts.ref("belief_revision", item.belief_revision_id) for item in changes
            ],
            snapshot_ref=reference,
            result_ref=reference,
            reason_codes=sorted(reasons),
            records=[
                *(facts.fact(facts.EVIDENCE, item.evidence_id, item) for item in evidence),
                *(facts.fact(facts.REVISION, item.belief_revision_id, item) for item in changes),
                facts.fact(facts.SNAPSHOT, identity, snapshot),
            ],
        )
