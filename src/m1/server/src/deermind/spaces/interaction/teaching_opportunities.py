"""教学机会以服务端提供的正式消息为依据。"""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid5

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, Ref
from deermind.spaces.interaction import history
from deermind.spaces.interaction import provision_facts as facts
from deermind.spaces.interaction.conversation_facts import record, ref
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


def started(
    scope: UUID,
    activity: history.ActivityState,
    input_id: UUID,
    now: datetime,
) -> facts.OpportunityStarted:
    identity = activity.identity
    opportunity_id = uuid5(input_id, "teaching-opportunity")
    body = facts.Opportunity(
        opportunity_id=opportunity_id,
        scope_id=scope,
        activity_id=identity.activity_id,
        adoption_ref=identity.adoption_ref,
        purpose=identity.name,
        opened_by_input=input_id,
        source_trigger_ref=None,
        created_at=now,
    )
    return facts.OpportunityStarted(
        opportunity_ref=ref("teaching_opportunity", opportunity_id),
        activity_ref=ref("activity", identity.activity_id, activity.position.revision),
        adoption_ref=Ref(owner="product", type="space_adoption", id=str(identity.adoption_ref)),
        records=[record(facts.OPPORTUNITY, opportunity_id, body)],
    )


async def opened(db: AsyncConnection, scope: UUID, activity: UUID) -> facts.Opportunity | None:
    row = await db.scalar(
        text(
            "SELECT to_jsonb(o)-'source_event_id' FROM interaction.teaching_opportunities o "
            "WHERE o.scope_id=:scope AND o.activity_id=:activity AND NOT EXISTS "
            "(SELECT 1 FROM interaction.opportunity_closures c "
            "WHERE c.opportunity_id=o.opportunity_id) ORDER BY o.created_at DESC LIMIT 1"
        ),
        {"scope": scope, "activity": activity},
    )
    return facts.Opportunity.model_validate_json(canonical_json(row)) if row else None


async def closed(
    db: AsyncConnection,
    scope: UUID,
    activity: history.ActivityState,
    source: UUID,
    base: EventDraft,
    reason: facts.CloseReason,
) -> EventDraft | None:
    opportunity = await opened(db, scope, activity.identity.activity_id)
    # 该活动没有未关闭的教学机会，无需生成关闭事件。
    if opportunity is None:
        return None
    rows = await db.scalars(
        text(
            "SELECT m.message_id FROM interaction.messages m "
            "JOIN interaction.message_assignments a ON a.message_id=m.message_id "
            "WHERE m.scope_id=:scope AND a.activity_id=:activity AND m.role='assistant' "
            "AND m.message_seq >= (SELECT first.message_seq FROM interaction.messages first "
            "WHERE first.scope_id=m.scope_id AND first.source_input_ref=:opening "
            "AND first.role='assistant' LIMIT 1) "
            "AND EXISTS (SELECT 1 FROM interaction.decision_records d "
            "WHERE d.scope_id=m.scope_id AND d.input_ref=m.source_input_ref "
            "AND d.accepted_action->>'action'='reply' "
            "AND d.proposal->>'intent' IN ('explanation','question_answer') "
            "AND d.proposal->>'question' IS NULL) "
            "ORDER BY m.message_seq"
        ),
        {
            "scope": scope,
            "activity": opportunity.activity_id,
            "opening": opportunity.opened_by_input,
        },
    )
    parts = [ref("message", item).model_copy(update={"path": "/parts/0"}) for item in rows]
    # 没有可纳入的讲解/答疑消息，不生成关闭事件。
    if not parts:
        return None
    identity = ref("opportunity_closure", opportunity.opportunity_id)
    event_id = uuid5(opportunity.opportunity_id, "closed")
    finished = facts.Closure(
        opportunity_id=opportunity.opportunity_id,
        provided_part_refs=parts,
        purpose=opportunity.purpose,
        close_reason=reason,
        closed_at=datetime.now(UTC),
        source_input_ref=source,
        source_trigger_ref=None,
        event_ref=event_id,
    )
    payload = facts.OpportunityClosed(
        opportunity_id=opportunity.opportunity_id,
        closure_ref=identity,
        activity_ref=ref("activity", opportunity.activity_id, activity.position.revision),
        adoption_ref=Ref(owner="product", type="space_adoption", id=str(opportunity.adoption_ref)),
        provided_part_refs=parts,
        purpose=opportunity.purpose,
        close_reason=reason,
        records=[record(facts.CLOSURE, opportunity.opportunity_id, finished)],
    )
    return replace(
        base,
        event_id=event_id,
        event_type=facts.CLOSED,
        owner_ref=identity,
        payload=payload.model_dump(mode="json"),
    )
