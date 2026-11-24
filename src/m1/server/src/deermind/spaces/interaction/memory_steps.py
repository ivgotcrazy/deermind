"""长交流只为当前活动概括已提交的旧消息。"""

from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import FactModel, Ref
from deermind.abstractions.executions import Execution, RunInput
from deermind.foundation.system.executions import store
from deermind.foundation.system.executions.contracts import Registry
from deermind.spaces.interaction import conversation_facts as facts
from deermind.spaces.interaction import history, memory_facts
from deermind.spaces.interaction.conversation import Conversation, draft, ref
from deermind.spaces.interaction.public import StudentInput, TextPart
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class SummaryMaterial(FactModel):
    activity: Ref
    previous: Ref | None
    covered_through: int
    covered_refs: list[Ref]
    older: list[dict[str, JsonValue]]
    earlier_summary: str | None


async def prepare(engine: AsyncEngine, registry: Registry, run: RunInput) -> SummaryMaterial | None:
    async with engine.begin() as db:
        work = await store.active(db, registry, run, "step")
        current = await history.current(db, work.scope_id)
        leaf = current.current_activity
        if not leaf or leaf.type not in {"explanation", "question_answer"}:
            return None
        activity = leaf.activity_ref.activity_id
        existing = await memory_facts.read(db, work.scope_id, activity)
        summary = next((value for value in existing if value.kind == "summary"), None)
        window = (
            await db.execute(
                text(
                    "SELECT m.message_id,m.message_seq,m.role,m.parts FROM interaction.messages m "
                    "JOIN interaction.message_assignments a ON a.message_id=m.message_id "
                    "WHERE m.scope_id=:scope AND a.activity_id=:activity "
                    "AND m.role IN ('student','assistant') AND m.message_seq>:after "
                    "AND m.source_input_ref IS DISTINCT FROM :input "
                    "ORDER BY m.message_seq LIMIT :limit"
                ),
                {
                    "scope": work.scope_id,
                    "activity": activity,
                    "after": summary.basis_message_seq if summary else 0,
                    "input": UUID(work.input_ref.id),
                    "limit": memory_facts.HISTORY_WINDOW,
                },
            )
        ).all()
        if len(window) < memory_facts.HISTORY_WINDOW:
            return None
        older: list[dict[str, JsonValue]] = [
            {"role": row.role, "parts": row.parts} for row in window[:6]
        ]
        old_refs = summary.content.get("covered_refs") if summary else None
        prior = (
            [Ref.model_validate(item) for item in old_refs] if isinstance(old_refs, list) else []
        )
        if len(canonical_json(older).encode()) > 16 * 1024 or len(prior) >= 60:
            return None
        earlier = summary.content.get("text") if summary else None
        return SummaryMaterial(
            activity=ref("activity", activity, leaf.activity_ref.revision),
            previous=summary.identity if summary else None,
            covered_through=window[5].message_seq,
            covered_refs=[*prior, *(ref("message", row.message_id) for row in window[:6])],
            older=older,
            earlier_summary=earlier if isinstance(earlier, str) else None,
        )


async def save(
    conversation: Conversation,
    registry: Registry,
    run: RunInput,
    material: SummaryMaterial,
    wording: str,
    candidate: UUID,
) -> None:
    if not 1 <= len(wording.strip()) <= 768:
        return
    async with conversation.engine.begin() as db:
        await store.lock_owned(db, registry, run.execution_id)
        work = await store.active(db, registry, run, "step")
        current = await history.current(db, work.scope_id)
        leaf = current.current_activity
        if (
            not leaf
            or ref("activity", leaf.activity_ref.activity_id, leaf.activity_ref.revision)
            != material.activity
        ):
            return
        history_rows = await memory_facts.read(db, work.scope_id, leaf.activity_ref.activity_id)
        prior = next((item for item in history_rows if item.kind == "summary"), None)
        if (prior.identity if prior else None) != material.previous:
            return
        authorization = await store.authorization(db, run.execution_id)
        request = await db.scalar(
            text("SELECT request_id FROM interaction.inputs WHERE input_id=:id"),
            {"id": UUID(work.input_ref.id)},
        )
        record = memory_facts.revise(
            work.scope_id,
            material.activity,
            work.input_ref,
            "summary",
            material.covered_through,
            {
                "text": wording,
                "covered_refs": [item.model_dump(mode="json") for item in material.covered_refs],
                "model_call_ref": Ref(owner="ai", type="candidate", id=str(candidate)).model_dump(
                    mode="json"
                ),
            },
            material.covered_refs,
            prior,
        )
        await conversation.append(
            db,
            work.scope_id,
            UUID(authorization.initiator_ref.id),
            UUID(work.acceptance_key),
            [draft(work.scope_id, memory_facts.SAVED, record.memory_ref, record, request)],
        )


async def remember_from_reply(
    db: AsyncConnection,
    work: Execution,
    message: facts.MessageFact,
    activity: history.ActivityState,
    proposal: memory_facts.Remember,
) -> memory_facts.MemorySaved | None:
    raw = await db.scalar(
        text("SELECT input FROM interaction.inputs WHERE scope_id=:scope AND input_id=:id"),
        {"scope": work.scope_id, "id": UUID(work.input_ref.id)},
    )
    original = StudentInput.model_validate_json(canonical_json(raw))
    items = await memory_facts.read(db, work.scope_id, activity.identity.activity_id)
    previous = next((value for value in items if value.kind == "entries"), None)
    provided = ref("message", message.message_id).model_copy(update={"path": "/parts/0"})
    first = message.parts[0]
    if not isinstance(first, TextPart):
        return None
    entries = memory_facts.remember(
        proposal, original.text or "", first.text, work.input_ref, provided, previous
    )
    if entries is None:
        return None
    return memory_facts.revise(
        work.scope_id,
        ref("activity", activity.identity.activity_id, activity.position.revision),
        work.input_ref,
        "entries",
        message.message_seq,
        {"entries": [item.model_dump(mode="json") for item in entries]},
        [work.input_ref, provided],
        previous,
    )
