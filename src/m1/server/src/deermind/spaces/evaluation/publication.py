"""Published evaluation state for other modules."""

from collections.abc import Sequence
from uuid import UUID

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Execution
from deermind.abstractions.waits import Match, Publication, ResultKey
from deermind.foundation.system.waits.results import ResultPolicy, publication
from deermind.spaces.evaluation import mastery_facts
from deermind.spaces.evaluation.goal_results import GoalResults
from deermind.spaces.evaluation.public import ClaimRef
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

BELIEF_RESULT = "belief_result"


def result_key(scope: UUID, trigger: UUID) -> ResultKey:
    return ResultKey(
        scope_id=scope, trigger_event_id=trigger, producer="evaluation", result_kind=BELIEF_RESULT
    )


async def check_result(db: AsyncConnection, run: Execution, saved: Publication) -> None:
    if run.input_ref.id != str(saved.trigger_event_id):
        raise PermissionError("Evaluation publication has a mismatched trigger")
    identity = await db.scalar(
        text("""
        SELECT snapshot_id FROM evaluation.mastery_snapshot
        WHERE scope_id=:scope AND source_event_id=:event
    """),
        {"scope": run.scope_id, "event": saved.event_id},
    )
    if identity is None:
        raise ValueError("Evaluation publication is missing a committed snapshot")
    reference = mastery_facts.ref("mastery_snapshot", identity)
    if saved.result_ref != reference or saved.publication_refs != [reference]:
        raise ValueError("Evaluation publication does not match its snapshot")


POLICY = ResultPolicy(
    producer="evaluation",
    kind=BELIEF_RESULT,
    readers=frozenset({"interaction", "evaluation", "product"}),
    check=check_result,
)


async def find_result(db: AsyncConnection, scope: UUID, trigger: UUID) -> Match | None:
    saved = await publication(db, result_key(scope, trigger))
    if saved is None:
        return None
    return Match(event_id=saved.event_id, result_ref=saved.result_ref)


class MasteryPublication:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    @staticmethod
    async def current_reference(db: AsyncConnection, scope: UUID) -> Ref | None:
        """Fix the published snapshot identity without expanding its contents."""
        identity = await db.scalar(
            text("SELECT current_snapshot_ref FROM evaluation.mastery_head WHERE scope_id=:scope"),
            {"scope": scope},
        )
        return mastery_facts.ref("mastery_snapshot", identity) if identity is not None else None

    async def read(
        self,
        scope: UUID,
        claims: Sequence[ClaimRef],
        pinned: Ref | None = None,
    ) -> dict[str, JsonValue]:
        if pinned is not None and (pinned.owner, pinned.type) != ("evaluation", "mastery_snapshot"):
            raise ValueError("Expected a mastery publication reference")
        async with self.engine.connect() as db:
            snapshot = await GoalResults.read_snapshot(db, scope, pinned)
        if snapshot is None:
            return {"state": "unknown", "snapshot_ref": None, "items": []}
        keys = {(claim.claim_id, claim.revision) for claim in claims}
        items: list[JsonValue] = [
            item.model_dump(mode="json", exclude={"source_refs", "evidence_coverage"})
            for item in snapshot.items
            if (item.claim_id, item.claim_revision) in keys
        ]
        return {
            "state": "available",
            "snapshot_ref": mastery_facts.ref("mastery_snapshot", snapshot.snapshot_id).model_dump(
                mode="json"
            ),
            "items": items,
        }
