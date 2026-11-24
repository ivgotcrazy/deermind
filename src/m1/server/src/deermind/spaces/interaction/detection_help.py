"""真实求助先提交检测轮结束，再交给讲解或答疑。"""

from datetime import UTC, datetime
from uuid import UUID, uuid5

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, InlineContent
from deermind.abstractions.executions import Execution, RunInput
from deermind.foundation.system.executions import store
from deermind.foundation.system.executions.contracts import Registry
from deermind.spaces.interaction import conversation_facts as facts
from deermind.spaces.interaction import help_facts, history, round_facts
from deermind.spaces.interaction.conversation import Conversation, draft, ref
from deermind.spaces.interaction.detection_plans import PlanProgress
from deermind.spaces.interaction.public import StudentInput
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def prepare_help(
    conversation: Conversation, registry: Registry, run: RunInput, quote: str | None
) -> bool:
    """只接受能在当前已受理原话中核实的求助。"""
    if not quote or not quote.strip():
        return False
    async with conversation.engine.begin() as db:
        await store.lock_owned(db, registry, run.execution_id)
        work = await store.active(db, registry, run, "step")
        current = await history.current(db, work.scope_id)
        leaf, opened = current.current_activity, current.current_round
        if not leaf or leaf.type != "detection" or not opened:
            return False
        source = (
            await db.execute(
                text(
                    "SELECT input,request_id FROM interaction.inputs "
                    "WHERE scope_id=:scope AND input_id=:id"
                ),
                {"scope": work.scope_id, "id": UUID(work.input_ref.id)},
            )
        ).one()
        accepted = StudentInput.model_validate_json(canonical_json(source.input))
        if quote not in (accepted.text or ""):
            return False
        if opened.state not in {"open", "closed"}:
            return False
        identity, now = UUID(work.input_ref.id), datetime.now(UTC)
        help_id = uuid5(identity, "help")
        existing = await db.scalar(
            text(
                "SELECT help_id FROM interaction.help_facts WHERE help_id=:id AND stage='handled'"
            ),
            {"id": help_id},
        )
        if existing is not None:
            return True
        closure = opened.round_ref
        events: list[EventDraft] = []
        progress = None
        if opened.state == "open" or opened.can_continue:
            closed, _ = await round_facts.close_payload(
                db,
                opened,
                identity,
                "help_requested",
                None,
                now,
            )
            if opened.state == "open":
                closure = closed.revision_ref
                events.append(
                    draft(work.scope_id, round_facts.CLOSED, closure, closed, source.request_id)
                )
            else:
                content = closed.records[1].content
                assert isinstance(content, InlineContent)
                progress = PlanProgress.model_validate_json(canonical_json(content.value))
        help_body = help_facts.payload(
            help_facts.HelpFact(
                help_id=help_id,
                stage="handled",
                scope_id=work.scope_id,
                source_input_ref=identity,
                activity_id=leaf.activity_ref.activity_id,
                task_use_id=UUID(opened.task_use_ref.id),
                classification="substantive",
                reason="student_requested_round_help",
                round_closure_ref=closure,
                provided_part_refs=[],
                created_at=now,
            ),
            work.input_ref,
            progress=progress,
        )
        events.append(
            draft(
                work.scope_id, help_facts.HANDLED, help_body.help_ref, help_body, source.request_id
            )
        )
        principal = UUID((await store.authorization(db, work.execution_id)).initiator_ref.id)
        await conversation.append(db, work.scope_id, principal, UUID(work.acceptance_key), events)
        return True


async def provided_help_event(
    db: AsyncConnection, work: Execution, message: facts.MessageFact, request: str
) -> EventDraft | None:
    row = await db.scalar(
        text(
            "SELECT to_jsonb(h)-'source_event_id' FROM interaction.help_facts h "
            "WHERE h.scope_id=:scope AND h.source_input_ref=:input AND h.stage='handled'"
        ),
        {"scope": work.scope_id, "input": UUID(work.input_ref.id)},
    )
    if row is None:
        return None
    handled = help_facts.HelpFact.model_validate_json(canonical_json(row))
    message_ref = ref("message", message.message_id)
    saved = handled.model_copy(
        update={
            "stage": "provided",
            "provided_part_refs": [message_ref.model_copy(update={"path": "/parts/0"})],
            "created_at": message.committed_at,
        }
    )
    body = help_facts.payload(saved, work.input_ref, message_ref)
    return draft(work.scope_id, help_facts.HANDLED, body.help_ref, body, request)
