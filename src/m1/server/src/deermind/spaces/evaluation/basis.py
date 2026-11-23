"""Read the evidence behind a fixed result or a source event."""

from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventFilter
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.public.errors import RequestError
from deermind.spaces.evaluation import mastery_facts as facts
from deermind.spaces.evaluation.public import (
    BasisView,
    BeliefChange,
    BeliefView,
    EvidenceQuote,
    EvidenceSummary,
    EvidenceView,
    GoalDecision,
    SourceExcerpt,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


def _missing() -> RequestError:
    return RequestError(404, "not_found", "找不到此学习空间内的评价依据。")


class EvaluationBasis:
    def __init__(self, engine: AsyncEngine, reader: EventReader) -> None:
        self.engine, self.reader = engine, reader

    @staticmethod
    async def _page(
        db: AsyncConnection, scope: UUID, references: Sequence[UUID], after: UUID | None, limit: int
    ) -> tuple[list[EvidenceSummary], str | None]:
        rows = (
            await db.execute(
                text("""
            SELECT evidence_id,aspect_code,qualification,verdict,reason,source_refs
            FROM evaluation.evidence
            WHERE scope_id=:scope AND evidence_id=ANY(CAST(:refs AS uuid[]))
                AND (CAST(:after AS uuid) IS NULL OR evidence_id>:after)
            ORDER BY evidence_id LIMIT :limit
        """),
                {"scope": scope, "refs": list(references), "after": after, "limit": limit + 1},
            )
        ).all()
        items = [
            EvidenceSummary(
                evidence_ref=facts.ref("evidence", row.evidence_id),
                aspect_code=row.aspect_code,
                qualification=row.qualification,
                verdict=row.verdict,
                reason=row.reason,
                source_event_refs=list(
                    dict.fromkeys(UUID(ref["event_id"]) for ref in row.source_refs)
                ),
            )
            for row in rows[:limit]
        ]
        return items, items[-1].evidence_ref.id if len(rows) > limit else None

    async def target(
        self, scope: UUID, identity: UUID, item: UUID, after: UUID | None, limit: int
    ) -> BasisView:
        async with self.engine.connect() as db:
            row = await db.scalar(
                text("""
                SELECT result FROM evaluation.goal_evaluation
                WHERE scope_id=:scope AND goal_evaluation_id=:id
            """),
                {"scope": scope, "id": identity},
            )
            if row is None:
                raise _missing()
            result = GoalDecision.model_validate_json(canonical_json(row))
            chosen = next((entry for entry in result.items if entry.item_id == item), None)
            if chosen is None:
                raise _missing()
            references = [
                UUID(ref.id)
                for method in chosen.methods
                for aspect in method.aspects
                for ref in aspect.evidence_refs
            ]
            items, cursor = await self._page(db, scope, references, after, limit)
        return BasisView(
            view="target",
            basis_ref=facts.ref("goal_evaluation", identity),
            items=items,
            next_cursor=cursor,
        )

    async def evidence(self, scope: UUID, identity: UUID, origin: UUID | None) -> BasisView:
        async with self.engine.connect() as db:
            row = await db.scalar(
                text("""
                SELECT to_jsonb(e)-'source_event_id' FROM evaluation.evidence e
                WHERE scope_id=:scope AND evidence_id=:id
            """),
                {"scope": scope, "id": identity},
            )
            change = await db.scalar(
                text("""
                SELECT to_jsonb(r) FROM (
                    SELECT update_kind,p_obs_before,p_obs_after,p_current_before,p_current_after,
                        parameter_ref,algorithm_ref FROM evaluation.belief_revision
                    WHERE scope_id=:scope AND evidence_ref=:id
                ) r
            """),
                {"scope": scope, "id": identity},
            )
        if row is None:
            raise _missing()
        entry = facts.EvidenceRecord.model_validate_json(canonical_json(row))
        excerpt = None
        if origin:
            refs = [ref for ref in entry.source_refs if ref.event_id == origin]
            if not refs:
                raise _missing()
            source = await self.reader.read_facts("learning_space", scope, origin, refs=refs)
            parts = source.get("items")
            if not isinstance(parts, list):
                raise ValueError("Incomplete evidence source")
            excerpt = SourceExcerpt(
                event_id=origin,
                content=[item["content"] for item in parts if isinstance(item, dict)],
            )
        return BasisView(
            view="evidence",
            basis_ref=facts.ref("evidence", identity),
            evidence=EvidenceView(
                evidence_id=entry.evidence_id,
                aspect_code=entry.aspect_code,
                qualification=entry.qualification,
                verdict=entry.verdict,
                reason=entry.reason,
                reason_codes=entry.reason_codes,
                source_refs=entry.source_refs,
                source_spans=[
                    EvidenceQuote(ref=span.ref, quote=span.quote) for span in entry.source_spans
                ],
                belief_change=BeliefChange.model_validate(change) if change is not None else None,
            ),
            source=excerpt,
        )

    async def from_event(
        self, scope: UUID, event: UUID, after: UUID | None, limit: int
    ) -> BasisView:
        meta = await self.reader.query_metadata(
            "learning_space", scope, filters=EventFilter(event_id=event), limit=1
        )
        if not meta["items"]:
            raise _missing()
        async with self.engine.connect() as db:
            references = (
                await db.scalars(
                    text("""
                SELECT e.evidence_id FROM evaluation.evidence e
                JOIN evaluation.evaluation_input i ON i.input_id=e.input_ref
                WHERE e.scope_id=:scope AND (e.source_event_id=:event OR i.trigger_event_id=:event
                    OR e.source_refs @> CAST(:source AS jsonb))
                AND (CAST(:after AS uuid) IS NULL OR e.evidence_id>:after)
                ORDER BY e.evidence_id LIMIT :limit
            """),
                    {
                        "scope": scope,
                        "event": event,
                        "after": after,
                        "limit": limit + 1,
                        "source": canonical_json([{"event_id": str(event)}]),
                    },
                )
            ).all()
            items, cursor = await self._page(db, scope, references, after, limit)
        return BasisView(view="event", items=items, next_cursor=cursor)

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
    ) -> BasisView:
        async with self.engine.connect() as db:
            row = await db.scalar(
                text("""
                SELECT to_jsonb(s)-'source_event_id' FROM evaluation.mastery_snapshot s
                WHERE scope_id=:scope AND snapshot_id=:id
            """),
                {"scope": scope, "id": snapshot},
            )
            if row is None:
                raise _missing()
            pinned = facts.MasterySnapshot.model_validate_json(canonical_json(row))
            key = (claim, revision, method, version, aspect)
            item = next(
                (
                    item
                    for item in pinned.items
                    if (
                        item.claim_id,
                        item.claim_revision,
                        item.method_id,
                        item.method_version,
                        item.aspect_code,
                    )
                    == key
                ),
                None,
            )
            if item is None:
                raise _missing()
            items, cursor = await self._page(
                db, scope, [UUID(ref.id) for ref in item.evidence_coverage], after, limit
            )
        return BasisView(
            view="belief",
            basis_ref=facts.ref("mastery_snapshot", snapshot),
            belief=BeliefView(
                p_obs=item.p_obs,
                p_current=item.p_current,
                last_observed_at=item.last_observed_at,
                belief_revision_ref=item.belief_revision_ref,
                observation_status=item.observation_status,
                unknown_reasons=item.unknown_reasons,
            ),
            items=items,
            next_cursor=cursor,
        )

    async def processing(self, scope: UUID, trigger: UUID) -> BasisView:
        async with self.engine.connect() as db:
            row = await db.scalar(
                text("""
                SELECT x.state FROM evaluation.evaluation_input i
                LEFT JOIN runtime.executions x ON x.scope_id=i.scope_id
                    AND x.acceptance_key=i.trigger_event_id::text
                WHERE i.scope_id=:scope AND i.trigger_event_id=:trigger
            """),
                {"scope": scope, "trigger": trigger},
            )
            accepted = row is not None or await db.scalar(
                text("""
                SELECT 1 FROM evaluation.evaluation_input
                WHERE scope_id=:scope AND trigger_event_id=:trigger
            """),
                {"scope": scope, "trigger": trigger},
            )
        state: Literal["not_found", "pending", "completed", "failed"] = "not_found"
        if accepted:
            state = (
                "completed"
                if row == "completed"
                else ("failed" if row in {"failed", "cancelled"} else "pending")
            )
        return BasisView(view="processing", processing=state)
