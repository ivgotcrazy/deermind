"""Derive a goal from the fixed adoption and preserve every completed calculation."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from deermind.abstractions.delivery import Acceptance, EventNotice
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import EventDraft, FactRecord, InlineContent, ProducerAccess, Ref
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore, lock_scope_sequence
from deermind.product.public.courses import AdoptionView
from deermind.spaces.evaluation import goal_facts as facts
from deermind.spaces.evaluation.goal_calculation import GoalKey, derive_target
from deermind.spaces.evaluation.public import GoalEvaluation
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

    async def receive(self, db: AsyncConnection, notice: EventNotice) -> Acceptance:
        scope, trigger = notice.scope_id, notice.event_id
        previous = await self._recorded(db, scope, trigger)
        if previous is not None:
            return Acceptance(disposition="accepted", arrangement_refs=[result_ref(previous)])
        data = await self.reader.read_facts(
            "learning_space",
            scope,
            trigger,
            expected_event_type=TRIGGER,
            refs=[EventPartRef(event_id=trigger, record_id=None, path="")],
        )
        parts = data["items"]
        assert isinstance(parts, list) and isinstance(parts[0], dict)
        payload = parts[0]["content"]
        assert isinstance(payload, dict)
        adoption_ref = Ref.model_validate(payload["adoption_ref"])
        basis_ref = Ref.model_validate(payload["target_basis_ref"])
        applied = await self.adoption(db, scope, UUID(adoption_ref.id))
        if applied.target_basis_ref != basis_ref or applied.adoption_ref != adoption_ref:
            raise ValueError("Goal trigger does not match its adoption")
        gaps = applied.snapshot.evaluation_gaps
        by_aspect: dict[GoalKey, list[str]] = {}
        for item in applied.snapshot.items:
            for method in item.methods:
                for gap in gaps:
                    if (gap.item_id, gap.method_id, gap.method_version) == (
                        item.item_id,
                        method.method_ref.object_id,
                        method.method_ref.version,
                    ):
                        by_aspect[item.item_id, method.method_ref, gap.aspect_code] = gap.reasons
        # E03 has no observations. E05 supplies the accepted mastery/evidence view.
        decision = derive_target(applied.snapshot.items, by_aspect, {})
        basis = await self.protect(db, scope)
        previous = await self._recorded(db, scope, trigger)
        if previous is not None:
            return Acceptance(disposition="accepted", arrangement_refs=[result_ref(previous)])
        current = (
            await db.execute(
                text(
                    "SELECT current_result_ref,target_basis_ref,mastery_publication_seq "
                    "FROM evaluation.goal_current WHERE scope_id=:scope"
                ),
                {"scope": scope},
            )
        ).one_or_none()
        reason = (
            "target_changed"
            if basis != UUID(basis_ref.id)
            else "already_current"
            if current and current.target_basis_ref == basis
            else None
        )
        now = datetime.now(UTC)
        planned = facts.CalculationInput(
            input_id=uuid4(),
            scope_id=scope,
            trigger_event_id=trigger,
            target_basis_ref=UUID(basis_ref.id),
            adoption_ref=UUID(adoption_ref.id),
            mastery_snapshot_ref=None,
            mastery_publication_seq=0,
            evidence_coverage=[],
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
            snapshot_ref=None,
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
            causation_event_id=trigger,
        )
        service = Ref(owner="evaluation", type="handler", id="evaluation.reassess_target")
        access = ProducerAccess(
            "evaluation", service, frozenset({event_scope}), frozenset({trigger})
        )
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
