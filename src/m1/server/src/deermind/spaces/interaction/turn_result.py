"""Persist one student turn result inside the owner transaction."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Execution, RunInput, State
from deermind.foundation.system.executions import commands, store
from deermind.foundation.system.executions.contracts import Registry
from deermind.spaces.interaction import conversation_facts as facts
from deermind.spaces.interaction import (
    history,
    memory_facts,
    provision_facts,
    teaching_opportunities,
)
from deermind.spaces.interaction.answer_feedback import read_answer_context
from deermind.spaces.interaction.conversation import (
    Conversation,
    assign_message,
    draft,
    message_event,
    next_position,
    ref,
    return_after_reply,
    store_position,
)
from deermind.spaces.interaction.detection_help import provided_help_event
from deermind.spaces.interaction.memory_steps import remember_from_reply
from deermind.spaces.interaction.public import (
    DetectionPlanPart,
    LearningTurnResult,
    TextPart,
)
from deermind.spaces.interaction.teaching_questions import (
    TeachingCard,
    presented_card,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

type TurnOutcome = Literal["completed", "needs_input", "blocked", "failed", "cancelled"]


@dataclass(frozen=True)
class Reply:
    text: str
    content: TeachingCard | DetectionPlanPart | None = None


@dataclass(frozen=True)
class TeachingReply:
    text: str
    memory: memory_facts.Remember | None


async def complete_turn(
    conversation: Conversation,
    db: AsyncConnection,
    registry: Registry,
    run: RunInput,
    work: Execution,
    outcome: TurnOutcome,
    reply: Reply | TeachingReply,
) -> None:
    """Commit the current result, receipt and release using the caller's transaction."""
    result = await _save_result(conversation, db, work, outcome, reply)
    await commands.complete(db, registry, run, result)
    await set_active_input(db, work.scope_id, None)


async def _save_result(
    service: Conversation,
    db: AsyncConnection,
    work: Execution,
    outcome: TurnOutcome,
    reply: Reply | TeachingReply | None,
    error: Ref | None = None,
) -> Ref:
    scope, input_id = work.scope_id, UUID(work.input_ref.id)
    content = reply.content if isinstance(reply, Reply) else None
    card = content if isinstance(content, TeachingCard) else None
    plan = content if isinstance(content, DetectionPlanPart) else None
    grant = await store.authorization(db, work.execution_id)
    principal = UUID(grant.initiator_ref.id)
    request_id = await db.scalar(
        text("SELECT request_id FROM interaction.inputs WHERE input_id=:id"), {"id": input_id}
    )
    sequence, epoch = await next_position(db, scope)
    current = await history.current(db, scope)
    leaf = current.current_activity
    activity = leaf.activity_ref.activity_id if leaf else None
    messages: list[UUID] = []
    if reply is not None:
        message = facts.MessageFact(
            message_id=uuid4(),
            scope_id=scope,
            message_seq=sequence,
            role="assistant",
            parts=[
                TextPart(part_id="text", type="text", text=reply.text),
                *([card.part] if card else []),
                *([plan] if plan else []),
            ],
            source_input_ref=input_id,
            source_trigger_ref=None,
            committed_at=datetime.now(UTC),
        )
        commands_to_save = [message_event(message, activity, request_id)]
        saved_activity = (
            await history.activity_at(db, scope, activity) if activity is not None else None
        )
        if isinstance(reply, TeachingReply) and saved_activity is not None:
            opportunity = await teaching_opportunities.opened(
                db, scope, saved_activity.identity.activity_id
            )
            if opportunity is None:
                opened = teaching_opportunities.started(
                    scope, saved_activity, input_id, message.committed_at
                )
                commands_to_save.append(
                    draft(
                        scope,
                        provision_facts.STARTED,
                        opened.opportunity_ref,
                        opened,
                        request_id,
                    )
                )
            provided = await provided_help_event(db, work, message, request_id)
            if provided:
                commands_to_save.append(provided)
            if reply.memory is not None:
                update = await remember_from_reply(db, work, message, saved_activity, reply.memory)
                if update:
                    commands_to_save.append(
                        draft(scope, memory_facts.SAVED, update.memory_ref, update, request_id)
                    )
        if card is not None and leaf is not None and activity is not None:
            assert saved_activity is not None
            if card.part.purpose == "practice":
                closure = await teaching_opportunities.closed(
                    db, scope, saved_activity, input_id, commands_to_save[0], "completed"
                )
                if closure:
                    commands_to_save.append(closure)
            commands_to_save.append(
                presented_card(scope, card, leaf, saved_activity, message, request_id)
            )
        if activity is not None:
            original = await db.scalar(
                text(
                    "SELECT to_jsonb(m)-'source_event_id' FROM interaction.messages m "
                    "WHERE scope_id=:scope AND source_input_ref=:input AND role='student'"
                ),
                {"scope": scope, "input": input_id},
            )
            if original is None and not await read_answer_context(db, input_id):
                raise RuntimeError("Accepted student input is missing its message")
            if original is not None:
                origin = facts.MessageFact.model_validate_json(canonical_json(original))
                commands_to_save.append(assign_message(origin, activity, request_id))
            commands_to_save.append(assign_message(message, activity, request_id))
        messages.append(message.message_id)
        next_leaf = activity
        if leaf is not None and leaf.run_state == "completed":
            next_leaf, sequence, notice_id, returning = await return_after_reply(
                db, scope, leaf, sequence, input_id, request_id
            )
            commands_to_save.extend(returning)
            messages.append(notice_id)
        await service.append(
            db,
            scope,
            principal,
            UUID(work.acceptance_key),
            commands_to_save,
            source_events=frozenset({card.supply_event_id}) if card else frozenset(),
        )
        if leaf and leaf.run_state == "completed" and saved_activity is not None:
            closure = await teaching_opportunities.closed(
                db, scope, saved_activity, input_id, commands_to_save[0], "completed"
            )
            if closure:
                await service.append(db, scope, principal, UUID(work.acceptance_key), [closure])
        await store_position(db, scope, next_leaf, sequence, epoch)
    result = _result(input_id, await reply_step(db, work), outcome, messages, error)
    result_ref = ref("input_result", result.result_id)
    current = await history.current(db, scope)
    snapshot = current.model_copy(
        update={
            "active_input_id": None,
            "allowed_actions": ["pause", "finish"] if current.current_activity else [],
        }
    )
    await service.append(
        db,
        scope,
        principal,
        UUID(work.acceptance_key),
        [
            draft(
                scope,
                facts.COMPLETED,
                result_ref,
                facts.InputCompleted(
                    records=[facts.record(facts.RESULT, result.result_id, result)],
                    input_ref=work.input_ref,
                    result_ref=result_ref,
                    turn_result=LearningTurnResult(
                        input_id=input_id,
                        message_refs=messages,
                        current=snapshot,
                        outcome=outcome,
                    ),
                ),
                request_id,
            )
        ],
    )
    return result_ref


async def finalize_turn(
    conversation: Conversation,
    db: AsyncConnection,
    work: Execution,
    state: State,
    cause: Ref | None,
) -> None:
    if state == "completed":
        return
    active = await history.current(db, work.scope_id)
    if active.active_input_id != UUID(work.input_ref.id):
        return
    if state == "cancelled":
        await _save_result(conversation, db, work, "cancelled", None)
    else:
        await _save_result(conversation, db, work, "failed", None, cause)
    await set_active_input(db, work.scope_id, None)


async def reply_step(db: AsyncConnection, work: Execution) -> str:
    if work.active_attempt_id is None:
        return "reply"
    attempt = await store.attempt(db, work.active_attempt_id)
    return "reply" if attempt.attempt_no == 1 else f"reply:{attempt.attempt_no}"


async def set_active_input(db: AsyncConnection, scope: UUID, identity: UUID | None) -> None:
    await db.execute(
        text("UPDATE interaction.space_runtime SET active_input_id=:id WHERE scope_id=:scope"),
        {"scope": scope, "id": identity},
    )


def _result(
    input_id: UUID, step: str, outcome: TurnOutcome, messages: list[UUID], error: Ref | None
) -> facts.InputResultFact:
    return facts.InputResultFact(
        result_id=uuid4(),
        input_id=input_id,
        step_key=step,
        outcome=outcome,
        message_refs=[ref("message", message) for message in messages],
        activity_revision_refs=[],
        error_ref=error,
        created_at=datetime.now(UTC),
    )
