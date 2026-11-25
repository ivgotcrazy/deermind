"""Derive a goal from the fixed adoption and preserve every completed calculation."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from deermind.abstractions.delivery import Acceptance, EventNotice
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import EventDraft, FactRecord, InlineContent, ProducerAccess, Ref
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore, lock_scope_sequence
from deermind.product.public.courses import AdoptionView
from deermind.spaces.domain.public import SolutionRef
from deermind.spaces.evaluation import goal_facts as facts
from deermind.spaces.evaluation import mastery_facts
from deermind.spaces.evaluation.goal_calculation import (
    BeliefKey,
    CoveredAnswer,
    GoalKey,
    Observation,
    derive_target,
)
from deermind.spaces.evaluation.inputs import find_prepared
from deermind.spaces.evaluation.public import ClaimRef, GoalEvaluation
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

type FixedAdoption = Callable[[AsyncConnection, UUID, UUID], Awaitable[AdoptionView]]
type ProtectBasis = Callable[[AsyncConnection, UUID], Awaitable[UUID]]
TRIGGER = "LearningTargetApplied"


def result_ref(identity: UUID) -> Ref:
    return Ref(owner="evaluation", type="goal_evaluation", id=str(identity))


class GoalResults:
    def __init__(
        self,
        store: EventStore,
        reader: EventReader,
        adoption: FixedAdoption,
        protect: ProtectBasis,
    ) -> None:
        self.store = store
        self.reader = reader
        self.adoption = adoption
        self.protect = protect

    async def _recorded(self, db: AsyncConnection, scope: UUID, trigger: UUID) -> UUID | None:
        return await db.scalar(
            text(
                "SELECT goal_evaluation_id FROM evaluation.goal_evaluation "
                "WHERE scope_id=:scope AND trigger_event_id=:trigger"
            ),
            {"scope": scope, "trigger": trigger},
        )

    @staticmethod
    async def progress(db: AsyncConnection, scope: UUID) -> Literal["pending", "failed"] | None:
        row = (
            await db.execute(
                text("""
            SELECT x.state, p.active_trigger_event_id
            FROM evaluation.evaluation_progress p
            LEFT JOIN runtime.executions x ON x.scope_id=p.scope_id
                AND x.acceptance_key=p.active_trigger_event_id::text
            WHERE p.scope_id=:scope
        """),
                {"scope": scope},
            )
        ).one_or_none()
        # 无进行中的触发，视为没有待办进度。
        if row is None or row.active_trigger_event_id is None:
            return None
        # 失败与取消归为 failed，其余在途状态记 pending。
        return "failed" if row.state in {"failed", "cancelled"} else "pending"

    async def receive(self, db: AsyncConnection, notice: EventNotice) -> Acceptance:
        scope, cause = notice.scope_id, notice.event_id
        is_mastery = notice.event_type == mastery_facts.COMPLETED
        data = await self.reader.read_facts(
            "learning_space",
            scope,
            cause,
            expected_event_type=notice.event_type,
            refs=[EventPartRef(event_id=cause, record_id=None, path="")],
        )
        parts = data["items"]
        assert isinstance(parts, list) and isinstance(parts[0], dict)
        payload = parts[0]["content"]
        assert isinstance(payload, dict)
        trigger = UUID(str(payload["trigger_event_id"])) if is_mastery else cause
        previous = await self._recorded(db, scope, trigger)
        # 该触发已算过目标结果，幂等返回既有结果引用。
        if previous is not None:
            return Acceptance(disposition="accepted", arrangement_refs=[result_ref(previous)])
        if is_mastery:
            prepared = await find_prepared(db, scope, trigger)
            input_ref = Ref.model_validate(payload["input_ref"])
            # 掌握结果必须挂在匹配的评价输入之下。
            if prepared is None or str(prepared.input_id) != input_ref.id:
                raise ValueError("Mastery result has no matching evaluation input")
            fixed = prepared.input
            applied = await self.adoption(db, scope, UUID(fixed.adoption_ref.id))
            # 采用视图的目标依据须与输入固定记录一致。
            if applied.target_basis_ref != fixed.target_basis_ref:
                raise ValueError("Evaluation input does not match its fixed target")
            pinned = Ref.model_validate(payload["snapshot_ref"])
        else:
            adoption_ref = Ref.model_validate(payload["adoption_ref"])
            basis_ref = Ref.model_validate(payload["target_basis_ref"])
            applied = await self.adoption(db, scope, UUID(adoption_ref.id))
            # 目标触发的采用引用与目标依据须与登记采用视图一致。
            if applied.target_basis_ref != basis_ref or applied.adoption_ref != adoption_ref:
                raise ValueError("Goal trigger does not match its adoption")
            pinned = None
        adoption_ref, basis_ref = applied.adoption_ref, applied.target_basis_ref
        snapshot = await self.read_snapshot(db, scope, pinned)
        gaps = applied.snapshot.evaluation_gaps
        by_aspect: dict[GoalKey, list[str]] = {}
        # 把教材差距按 目标项 → 解法 → 方面 归集到对应决策键。
        for item in applied.snapshot.items:
            for method in item.methods:
                for gap in gaps:
                    if (gap.item_id, gap.method_id, gap.method_version) == (
                        item.item_id,
                        method.method_ref.object_id,
                        method.method_ref.version,
                    ):
                        by_aspect[item.item_id, method.method_ref, gap.aspect_code] = gap.reasons
        observations = await self._observations(db, snapshot) if snapshot is not None else {}
        decision = derive_target(applied.snapshot.items, by_aspect, observations)
        basis = await self.protect(db, scope)
        previous = await self._recorded(db, scope, trigger)
        # 计算完成后二次查重，防止并发重复落目标结果。
        if previous is not None:
            return Acceptance(disposition="accepted", arrangement_refs=[result_ref(previous)])
        current = (
            await db.execute(
                text(
                    "SELECT c.current_result_ref,c.target_basis_ref,"
                    "c.mastery_publication_seq,g.result "
                    "FROM evaluation.goal_current c LEFT JOIN evaluation.goal_evaluation g "
                    "ON g.goal_evaluation_id=c.current_result_ref WHERE c.scope_id=:scope"
                ),
                {"scope": scope},
            )
        ).one_or_none()
        sequence = snapshot.publication_seq if snapshot else 0
        reason = None
        # 目标依据已变更，本次结果不应用为当前态。
        if basis != UUID(basis_ref.id):
            reason = "target_changed"
        # 所用掌握快照发布序号早于当前已持有的，属于旧快照。
        elif current and sequence < current.mastery_publication_seq:
            reason = "older_snapshot"
        # 同一依据、同一快照序号下已存在结果，须与本次计算逐字节一致。
        elif (
            current
            and current.target_basis_ref == basis
            and current.mastery_publication_seq == sequence
        ):
            if canonical_json(current.result) != canonical_json(decision.model_dump(mode="json")):
                raise ValueError("Goal calculation conflicts with a result on the same basis")
            reason = "already_current"
        now = datetime.now(UTC)
        planned = facts.CalculationInput(
            input_id=uuid4(),
            scope_id=scope,
            trigger_event_id=trigger,
            target_basis_ref=UUID(basis_ref.id),
            adoption_ref=UUID(adoption_ref.id),
            mastery_snapshot_ref=snapshot.snapshot_id if snapshot else None,
            mastery_publication_seq=sequence,
            evidence_coverage=[
                answer.evidence_ref.model_dump(mode="json")
                for observation in observations.values()
                for answer in observation.covered_answers
            ],
            calculation_rule_ref="M1-GOAL-THRESHOLD-01",
            planned_result_id=uuid4(),
            created_at=now,
        )
        result = GoalEvaluation(
            goal_evaluation_id=planned.planned_result_id,
            scope_id=scope,
            trigger_event_id=trigger,
            input_ref=planned.input_id,
            target_basis_ref=planned.target_basis_ref,
            previous_current_ref=current.current_result_ref if current else None,
            current_state_applied=reason is None,
            result=decision,
            created_at=now,
        )
        reference = result_ref(result.goal_evaluation_id)
        body = facts.GoalCompleted(
            trigger_event_id=trigger,
            goal_evaluation_ref=reference,
            target_basis_ref=basis_ref,
            snapshot_ref=mastery_facts.ref("mastery_snapshot", snapshot.snapshot_id)
            if snapshot
            else None,
            result_ref=reference,
            previous_current_ref=result_ref(result.previous_current_ref)
            if result.previous_current_ref
            else None,
            current_state_applied=result.current_state_applied,
            not_applied_reason=reason,
            records=[
                FactRecord(
                    record_id=str(identity),
                    record_type=kind,
                    schema_version=1,
                    content=InlineContent(storage="inline", value=value.model_dump(mode="json")),
                )
                for identity, kind, value in (
                    (planned.input_id, facts.INPUT, planned),
                    (result.goal_evaluation_id, facts.RESULT, result),
                )
            ],
        )
        event_scope = ("learning_space", scope)
        draft = EventDraft(
            uuid4(),
            facts.COMPLETED,
            1,
            *event_scope,
            reference,
            body.model_dump(mode="json"),
            None,
            causation_event_id=cause,
        )
        service = Ref(owner="evaluation", type="handler", id="evaluation.reassess_target")
        access = ProducerAccess("evaluation", service, frozenset({event_scope}), frozenset({cause}))
        sequence = await lock_scope_sequence(db, *event_scope)
        (stored,) = await self.store.append(
            db,
            access,
            (draft,),
            commit_id=uuid4(),
            correlation_id=notice.handoff_id,
            expected_seq={event_scope: sequence},
        )
        await facts.project(db, stored)
        return Acceptance(disposition="accepted", arrangement_refs=[reference])

    @staticmethod
    async def read_snapshot(
        db: AsyncConnection, scope: UUID, pinned: Ref | None
    ) -> mastery_facts.MasterySnapshot | None:
        # 指定了快照引用时按编号回读，否则取范围当前头快照。
        if pinned:
            row = await db.scalar(
                text("""
                SELECT to_jsonb(s)-'source_event_id' FROM evaluation.mastery_snapshot s
                WHERE s.scope_id=:scope AND s.snapshot_id=:id
            """),
                {"scope": scope, "id": UUID(pinned.id)},
            )
            # 指定快照不存在于本空间，判引用越界。
            if row is None:
                raise ValueError("Goal calculation snapshot does not belong to this space")
        else:
            row = await db.scalar(
                text("""
                SELECT to_jsonb(s)-'source_event_id'
                FROM evaluation.mastery_head h
                JOIN evaluation.mastery_snapshot s ON s.snapshot_id=h.current_snapshot_ref
                WHERE h.scope_id=:scope
            """),
                {"scope": scope},
            )
        return (
            mastery_facts.MasterySnapshot.model_validate_json(canonical_json(row)) if row else None
        )

    @staticmethod
    async def _observations(
        db: AsyncConnection, snapshot: mastery_facts.MasterySnapshot
    ) -> dict[BeliefKey, Observation]:
        by_item: dict[BeliefKey, list[CoveredAnswer]] = {}
        rows = (
            await db.execute(
                text("""
            SELECT e.evidence_id,e.claim_id,e.claim_revision,e.method_id,e.method_version,
                e.aspect_code,e.qualification,e.condition_facts
            FROM evaluation.evidence e
            JOIN evaluation.mastery_snapshot s ON s.source_event_id=e.source_event_id
            WHERE e.scope_id=:scope AND e.source_kind='answer' AND s.publication_seq<=:seq
            ORDER BY s.publication_seq DESC, e.evidence_id
        """),
                {"scope": snapshot.scope_id, "seq": snapshot.publication_seq},
            )
        ).all()
        for row in rows:
            key = (
                ClaimRef(claim_id=row.claim_id, revision=row.claim_revision),
                SolutionRef(kind="solution", object_id=row.method_id, version=row.method_version),
                str(row.aspect_code),
            )
            # 取已知条件值，排除专用范围条件（范围单独收集）。
            conditions = {
                item["condition"]: item["value"]
                for item in row.condition_facts
                if item["status"] == "known" and item["condition"] != "target_scope"
            }
            # 收集已知的目标范围取值，供佐证按范围匹配。
            scopes = [
                item["value"]
                for item in row.condition_facts
                if item["condition"] == "target_scope" and item["status"] == "known"
            ]
            by_item.setdefault(key, []).extend(
                CoveredAnswer(
                    mastery_facts.ref("evidence", row.evidence_id),
                    row.qualification,
                    conditions,
                    scope,
                )
                for scope in (scopes or [None])
            )
        result: dict[BeliefKey, Observation] = {}
        # 按快照中的方面逐项装配观测值与佐证列表。
        for item in snapshot.items:
            key = (
                ClaimRef(claim_id=item.claim_id, revision=item.claim_revision),
                SolutionRef(kind="solution", object_id=item.method_id, version=item.method_version),
                str(item.aspect_code),
            )
            result[key] = Observation(
                Decimal(str(item.p_obs)) if item.p_obs is not None else None,
                by_item.get(key, ()),
            )
        return result

    @staticmethod
    async def current(
        db: AsyncConnection, scope: UUID, target_basis: UUID
    ) -> GoalEvaluation | None:
        raw: JsonValue = await db.scalar(
            text(
                "SELECT to_jsonb(g)-'source_event_id' FROM evaluation.goal_current c "
                "JOIN evaluation.goal_evaluation g ON g.goal_evaluation_id=c.current_result_ref "
                "WHERE c.scope_id=:scope AND c.target_basis_ref=:basis"
            ),
            {"scope": scope, "basis": target_basis},
        )
        return None if raw is None else GoalEvaluation.model_validate_json(canonical_json(raw))

    @staticmethod
    async def current_reference(
        db: AsyncConnection, scope: UUID, target_basis: UUID
    ) -> UUID | None:
        """Identify the current result without expanding the target decision."""
        return await db.scalar(
            text(
                "SELECT current_result_ref FROM evaluation.goal_current "
                "WHERE scope_id=:scope AND target_basis_ref=:basis"
            ),
            {"scope": scope, "basis": target_basis},
        )

    @staticmethod
    async def fixed_result(
        db: AsyncConnection, scope: UUID, target_basis: UUID, identity: UUID
    ) -> GoalEvaluation | None:
        """Read a previously published result for the specified adopted target."""
        raw: JsonValue = await db.scalar(
            text(
                "SELECT to_jsonb(g)-'source_event_id' FROM evaluation.goal_evaluation g "
                "WHERE g.scope_id=:scope AND g.target_basis_ref=:basis "
                "AND g.goal_evaluation_id=:id AND g.current_state_applied"
            ),
            {"scope": scope, "basis": target_basis, "id": identity},
        )
        return None if raw is None else GoalEvaluation.model_validate_json(canonical_json(raw))
