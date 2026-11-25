"""Save student answers and record their actual performance."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid5

from deermind.abstractions.events import EventDraft, Ref
from deermind.abstractions.executions import Execution
from deermind.foundation.system.executions import store
from deermind.foundation.system.public.errors import RequestError
from deermind.spaces.interaction import conversation_facts as facts
from deermind.spaces.interaction import (
    help_facts,
    history,
    round_facts,
    task_facts,
    teaching_opportunities,
)
from deermind.spaces.interaction.conversation import Conversation, draft, ref
from deermind.spaces.interaction.public import (
    AnswerCommand,
    CurrentConversation,
    LearningInputAcceptance,
)
from deermind.spaces.interaction.reply_candidate import ReplyCandidate
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class AnswerContext:
    submission_id: UUID
    task_use_ref: UUID
    instance_ref: Ref
    answer: dict[str, JsonValue]
    request_id: str
    round_id: UUID | None


async def read_answer_context(db: AsyncConnection, source: UUID) -> AnswerContext | None:
    row = (
        await db.execute(
            text(
                "SELECT s.submission_id,s.answer,s.task_use_ref,t.instance_ref, "
                "i.request_id,s.round_id "
                "FROM interaction.submissions s "
                "JOIN interaction.task_uses t ON t.task_use_id=s.task_use_ref "
                "JOIN interaction.inputs i ON i.input_id=s.source_input_ref "
                "WHERE s.source_input_ref=:id AND t.purpose IN ('practice','detection')"
            ),
            {"id": source},
        )
    ).one_or_none()
    # 命中作答上下文则组装对象，无记录返回空。
    return (
        AnswerContext(
            row.submission_id,
            row.task_use_ref,
            Ref.model_validate(row.instance_ref),
            row.answer,
            row.request_id,
            row.round_id,
        )
        if row
        else None
    )


async def save_answer_feedback(
    conversation: Conversation,
    db: AsyncConnection,
    work: Execution,
    candidate: ReplyCandidate,
    candidate_id: UUID,
    practice: AnswerContext,
) -> None:
    """Save feedback in the caller's transaction for the accepted answer."""
    assert candidate.verdict is not None
    identity = uuid5(work.execution_id, "answer-feedback")
    owner, submission = (
        ref("answer_feedback", identity),
        ref("submission", practice.submission_id),
    )
    facts_used = [ref("task_use", practice.task_use_ref), practice.instance_ref, submission]
    record = task_facts.AnswerFeedbackFact(
        feedback_id=identity,
        submission_id=practice.submission_id,
        verdict=candidate.verdict,
        basis_refs=facts_used,
        feedback={
            "schema_version": "1",
            "role": "reference",
            "source_refs": [],
            "data_tables": [],
            "blocks": [
                {
                    "block_id": "feedback",
                    "type": "paragraph",
                    "provenance": {"source_refs": [], "transformation": "generated"},
                    "payload": {"spans": [{"type": "text", "text": candidate.wording}]},
                }
            ],
        },
        # 判定为不确定时标注证据局限，其余不留限制项。
        limitations=["uncertain"] if candidate.verdict == "uncertain" else [],
        run_ref=work.execution_id,
        created_at=datetime.now(UTC),
    )
    principal = UUID((await store.authorization(db, work.execution_id)).initiator_ref.id)
    event = draft(
        work.scope_id,
        task_facts.FEEDBACK,
        owner,
        task_facts.AnswerFeedbackPrepared(
            feedback_ref=owner,
            submission_ref=submission,
            source_input_ref=work.input_ref,
            records=[facts.record(task_facts.ANSWER_FEEDBACK, identity, record)],
        ),
        practice.request_id,
    )
    await conversation.append(
        db,
        work.scope_id,
        principal,
        UUID(work.acceptance_key),
        [
            replace(event, subject_refs=(Ref(owner="ai", type="candidate", id=str(candidate_id)),)),
        ],
    )


async def save_submission(
    conversation: Conversation,
    db: AsyncConnection,
    scope: UUID,
    principal: UUID,
    acceptance: LearningInputAcceptance,
    practice: AnswerCommand,
    current: CurrentConversation,
) -> None:
    leaf = current.current_activity
    if leaf is None or leaf.activity_ref != practice.activity_ref or leaf.run_state != "active":
        # 活动已切换或非活跃；若所引轮次已闭环，优先报轮次结束。
        if practice.round_ref and current.current_round and current.current_round.state == "closed":
            raise RequestError(409, "round_closed", "当前检测轮已经结束。")
        raise RequestError(409, "revision_conflict", "作答所属活动已变动。")
    if practice.task_use_ref.owner != "interaction" or practice.task_use_ref.type != "task_use":
        # 引用必须指向本空间内的练习使用记录。
        raise RequestError(400, "invalid_reference", "请选择本次活动中的练习。")
    try:
        use_id = UUID(practice.task_use_ref.id)
    except ValueError as error:
        # 编号非合法 UUID，转换为无效引用错误。
        raise RequestError(400, "invalid_reference", "练习编号无效。") from error
    opened = current.current_round if practice.round_ref else None
    if practice.round_ref:
        if opened is None or opened.state != "open":
            # 所引轮次不存在或已闭环，不能再提交。
            raise RequestError(409, "round_closed", "当前检测轮已经结束。")
        if (
            opened.round_ref != practice.round_ref
            or opened.round_ref.revision != practice.expected_round_revision
            or opened.task_use_ref != practice.task_use_ref
        ):
            # 轮次引用、修订与题目实例须与当前轮一致。
            raise RequestError(409, "revision_conflict", "检测题目或轮次已变化。")
    elif practice.expected_round_revision is not None:
        # 教学练习不带检测轮，却提供了轮次修订，引用非法。
        raise RequestError(400, "invalid_reference", "教学练习没有检测轮。")
    use = (
        await db.execute(
            text(
                "SELECT adoption_ref,source_event_id FROM interaction.task_uses "
                "WHERE task_use_id=:id "
                "AND scope_id=:scope AND activity_id=:activity "
                "AND purpose=:purpose AND round_id IS NOT DISTINCT FROM CAST(:round AS uuid)"
            ),
            {
                "id": use_id,
                "scope": scope,
                "activity": leaf.activity_ref.activity_id,
                "purpose": "detection" if opened else "practice",
                "round": UUID(opened.round_ref.id) if opened else None,
            },
        )
    ).one_or_none()
    if use is None:
        # 练习使用记录在当前活动/轮次范围内不存在。
        raise RequestError(404, "not_found", "找不到此练习。")
    if await db.scalar(
        text("SELECT 1 FROM interaction.submissions WHERE submission_id=:id"),
        {"id": practice.submission_id},
    ):
        # 作答编号已被占用，避免重复提交。
        raise RequestError(409, "identity_conflict", "该作答编号已经使用。")
    identity = ref("submission", practice.submission_id)
    event_id = uuid5(acceptance.input_id, "answer-submitted")
    now = datetime.now(UTC)
    item = task_facts.SubmissionFact(
        submission_id=practice.submission_id,
        scope_id=scope,
        source_input_ref=acceptance.input_id,
        task_use_ref=use_id,
        activity_id=leaf.activity_ref.activity_id,
        round_id=UUID(opened.round_ref.id) if opened else None,
        answer=practice.answer.model_dump(mode="json"),
        help_basis=await help_facts.answer_basis(
            db, scope, use_id, use.source_event_id, "detection" if opened else "practice"
        ),
        adoption_ref=use.adoption_ref,
        accepted_at=now,
        event_ref=event_id,
    )
    event = draft(
        scope,
        task_facts.SUBMITTED,
        identity,
        task_facts.AnswerSubmitted(
            submission_ref=identity,
            task_use_ref=practice.task_use_ref,
            activity_ref=ref("activity", leaf.activity_ref.activity_id, leaf.activity_ref.revision),
            round_ref=opened.round_ref if opened else None,
            plan_ref=ref("detection_plan", opened.plan_ref.plan_id, opened.plan_ref.revision)
            if opened
            else None,
            adoption_ref=Ref(owner="product", type="space_adoption", id=str(use.adoption_ref)),
            help_basis_ref=identity.model_copy(update={"path": "/help_basis"}),
            records=[facts.record(task_facts.SUBMISSION, practice.submission_id, item)],
        ),
        practice.request_id,
    )
    events: list[EventDraft] = []
    position = await history.activity_at(db, scope, leaf.activity_ref.activity_id)
    closure = await teaching_opportunities.closed(
        db, scope, position, acceptance.input_id, event, "completed"
    )
    if closure:
        # 作答完成后可闭环教学机会，追加关闭事件。
        events.append(closure)
    events.append(replace(event, event_id=event_id))
    if opened:
        # 检测轮提交后，按提交原因生成闭轮事件。
        closed, _next = await round_facts.close_payload(
            db,
            opened,
            acceptance.input_id,
            "submitted",
            identity,
            now,
        )
        events.append(
            draft(scope, round_facts.CLOSED, closed.revision_ref, closed, practice.request_id)
        )
    await conversation.append(db, scope, principal, acceptance.request_ref, events)
