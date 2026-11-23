"""学生输入、后台工作与终态使用同一空间顺序。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from deermind.abstractions.ai.contracts import ExecutionConfig
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import EventDraft, Ref
from deermind.abstractions.executions import Authorization, Execution, RunInput, State
from deermind.abstractions.waits import WaitCall
from deermind.foundation.ai import store as ai_store
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.executions import commands, store
from deermind.foundation.system.executions.contracts import Caller, Entry, Registry
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.foundation.system.waits.service import Waits
from deermind.product.public.authentication import AccountView
from deermind.product.public.courses import CourseSnapshot
from deermind.spaces.domain.public import TaskInstance
from deermind.spaces.interaction import conversation_facts as facts
from deermind.spaces.interaction import (
    help_facts,
    history,
    memory_facts,
    provision_facts,
    round_facts,
    task_facts,
    teaching_opportunities,
)
from deermind.spaces.interaction.blueprints import effective_binding, entry_node
from deermind.spaces.interaction.conversation import (
    SCOPE,
    Conversation,
    activity_change,
    assign_message,
    draft,
    event_access,
    lock_position,
    message_event,
    next_position,
    notice_events,
    ref,
    return_point,
    revise,
    store_position,
)
from deermind.spaces.interaction.public import (
    CONTROL_ACTIVITY,
    HANDLE_INPUT,
    PREPARE_DETECTION,
    SUBMIT_ANSWER,
    ActivityControlReceipt,
    ActivityControlResult,
    ActivityType,
    AnswerCommand,
    AnswerReceipt,
    BlueprintNode,
    ConfigView,
    CurrentConversation,
    DetectionPlanPart,
    LearningInputAcceptance,
    LearningInputCommand,
    LearningTurnResult,
    PrepareDetectionCommand,
    RetryLearningWork,
    StopReply,
    StudentInput,
    TextPart,
)
from deermind.spaces.interaction.reply_candidate import ReplyCandidate
from deermind.spaces.interaction.teaching_flow import TeachingDecision, decide
from deermind.spaces.interaction.teaching_questions import (
    TeachingCard,
    TeachingQuestion,
    teaching_options,
    wait_for_question,
)
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncConnection

WORKFLOW = "interaction.handle_input"
ACKNOWLEDGE_ANSWER = "acknowledge_detection_answer"
type SpaceAdoption = Callable[[AsyncConnection, UUID, bool], Awaitable[UUID]]
type ActivityConfig = Callable[
    [UUID, UUID, ActivityType, UUID | None], Awaitable[tuple[ConfigView | None, CourseSnapshot]]
]
type TurnOutcome = Literal["completed", "needs_input", "blocked", "failed", "cancelled"]
type ReadQuestion = Callable[[AsyncConnection, Ref], Awaitable[TaskInstance | None]]
type ReadChapter = Callable[[UUID, UUID, Ref], Awaitable[list[dict[str, JsonValue]]]]


@dataclass(frozen=True)
class AnswerContext:
    submission_id: UUID
    task_use_ref: UUID
    instance_ref: Ref
    answer: dict[str, JsonValue]
    request_id: str
    round_id: UUID | None


def _caller(principal: UUID, scope: UUID, action: str) -> Caller:
    return Caller(
        Ref(owner="product", type="account", id=str(principal)),
        "interaction",
        frozenset({(SCOPE, scope)}),
        frozenset({action}),
    )


class StudentTurns:
    """空间内只接受一个交流输入，完成和停止竞争同一提交资格。"""

    def __init__(
        self,
        conversation: Conversation,
        current_adoption: SpaceAdoption,
        attachments: FactAttachments,
        queue: str,
        config: ExecutionConfig | None,
        activity_config: ActivityConfig,
        read_chapter: ReadChapter,
    ) -> None:
        self.conversation = conversation
        self.engine = conversation.engine
        self.current_adoption = current_adoption
        self.attachments = attachments
        self.config = config
        self.activity_config = activity_config
        self.read_chapter = read_chapter
        self.registry = Registry(
            [
                Entry(
                    "interaction",
                    entry,
                    "ai_operation",
                    Ref(owner="interaction", type="operation", id=entry, version=1),
                    WORKFLOW,
                    queue,
                    self._lock,
                    self._check,
                    self._finalize,
                )
                for entry in (HANDLE_INPUT, PREPARE_DETECTION)
            ]
        )

    async def _lock(self, db: AsyncConnection, kind: str, scope: UUID) -> None:
        if kind != SCOPE:
            raise PermissionError("Expected learning space")
        await self.current_adoption(db, scope, True)
        await lock_position(db, scope)

    async def check_space(self, account: AccountView, scope: UUID) -> None:
        async with self.engine.connect() as db:
            await self.conversation.authorize(db, account, scope, False)

    async def _check(
        self, db: AsyncConnection, work: Execution, authorization: Authorization, action: str
    ) -> None:
        if action in {"read", "cancel"}:
            return
        scope, input_id = work.scope_id, UUID(work.input_ref.id)
        basis = await self.current_adoption(db, scope, False)
        if action == "retry":
            valid = await db.scalar(
                text(
                    "SELECT 1 FROM interaction.inputs i JOIN interaction.space_runtime p "
                    "ON p.scope_id=i.scope_id WHERE i.scope_id=:scope AND i.input_id=:id "
                    "AND p.active_input_id IS NULL AND p.turn_epoch=i.turn_epoch"
                ),
                {"scope": scope, "id": input_id},
            )
            if not valid or str(basis) != authorization.basis_refs[0].id:
                raise RequestError(409, "revision_conflict", "当前交流已变化，无法重试原请求。")
            await self._occupy(db, scope, input_id)
            return
        found = await db.scalar(
            text(
                "SELECT i.input_id FROM interaction.inputs i "
                "JOIN interaction.space_runtime p ON p.scope_id=i.scope_id "
                "WHERE i.scope_id=:scope AND i.input_id=:id AND p.active_input_id=i.input_id "
                "AND p.turn_epoch=i.turn_epoch"
            ),
            {"scope": scope, "id": input_id},
        )
        if found != input_id or str(basis) != authorization.basis_refs[0].id:
            raise PermissionError("Input no longer owns the space or adopted basis")

    async def _read_part(
        self, scope: UUID, event: UUID, request: UUID, event_type: str, path: str
    ) -> str:
        payload = await self.conversation.reader.read_facts(
            SCOPE,
            scope,
            event,
            refs=[EventPartRef(event_id=event, record_id=None, path=path)],
            expected_event_type=event_type,
            correlation_id=request,
        )
        items = payload["items"]
        assert isinstance(items, list) and isinstance(items[0], dict)
        return canonical_json(items[0]["content"])

    async def accept(
        self,
        account: AccountView,
        scope: UUID,
        command: LearningInputCommand,
        *,
        practice: AnswerCommand | None = None,
        preparing_detection: bool = False,
    ) -> LearningInputAcceptance:
        """原文可被外置。准备内容后重查采用与空间顺序，才共同提交。"""
        entry = PREPARE_DETECTION if preparing_detection else HANDLE_INPUT
        action = SUBMIT_ANSWER if practice else entry
        normalized: dict[str, JsonValue] = {
            "digest": sha256(
                canonical_json((practice or command.input).model_dump(mode="json")).encode()
            ).hexdigest()
        }
        principal = account.account_id
        service = self.conversation
        async with self.engine.connect() as db:
            adoption = await service.authorize(db, account, scope, False)
            saved = await service.receipts.find_completed_request(
                db, principal, action, scope, command.request_id, normalized
            )
            before = await history.current(db, scope)
            epoch = (
                await db.scalar(
                    text("SELECT turn_epoch FROM interaction.space_runtime WHERE scope_id=:scope"),
                    {"scope": scope},
                )
                or 0
            )
        if saved is not None:
            assert saved.result_ref is not None
            return await self._read_acceptance(scope, UUID(saved.result_ref.id), saved.request_ref)
        if (
            practice
            and practice.round_ref
            and before.current_round
            and before.current_round.round_ref.id == practice.round_ref.id
            and before.current_round.state == "closed"
        ):
            raise RequestError(409, "round_closed", "当前检测轮已经结束。")
        if before.active_input_id is not None:
            raise RequestError(409, "interaction_busy", "正在处理上一条，草稿已保留。")
        if command.input.attachment_refs:
            raise RequestError(400, "invalid_reference", "当前聊天只接收文字和教材引用。")
        references = command.input.explicit_refs
        if references:
            available = [
                Ref(
                    owner="product", type="chapter", id=str(item.chapter_id), revision=item.revision
                )
                for item in adoption.snapshot.chapters
            ]
            available.extend(
                content
                for chapter in adoption.snapshot.chapters
                for content in chapter.content_refs
            )
            if len(references) > 1 or references[0] not in available:
                raise RequestError(404, "not_found", "引用的教材内容不在当前采用范围内。")
        config = self.config
        if config is None:
            raise RequestError(503, "configuration_unavailable", "学习助手尚未配置模型。")
        response = LearningInputAcceptance(
            request_ref=uuid4(), execution_ref=uuid4(), input_id=uuid4()
        )
        identity = ref("input", response.input_id)
        now = datetime.now(UTC)
        original = facts.InputFact(
            input_id=response.input_id,
            scope_id=scope,
            request_id=command.request_id,
            kind="answer" if practice else "activity_control" if preparing_detection else "message",
            input=command.input.model_dump(mode="json"),
            turn_epoch=epoch + 1,
            accepted_at=now,
        )
        accepted = draft(
            scope,
            facts.ACCEPTED,
            identity,
            facts.InputAccepted(
                records=[facts.record(facts.INPUT, original.input_id, original)],
                input_ref=identity,
                adoption_ref=adoption.adoption_ref,
                acceptance=response,
            ),
            command.request_id,
        )
        sequence = before.latest_message_seq + 1
        user_message = facts.MessageFact(
            message_id=uuid4(),
            scope_id=scope,
            message_seq=sequence,
            role="student",
            parts=[TextPart(part_id="text", type="text", text=command.input.text or "")],
            source_input_ref=response.input_id,
            source_trigger_ref=None,
            committed_at=now,
        )
        prepared = await self.attachments.prepare(
            service.events,
            event_access(scope, principal),
            (accepted,)
            if practice
            else (accepted, message_event(user_message, None, command.request_id)),
        )
        async with self.engine.begin() as db:
            receipt = await service.receipts.claim_request(
                db,
                principal_id=str(principal),
                action=action,
                scope_id=str(scope),
                request_id=command.request_id,
                normalized_input=normalized,
                reserved_ref=response.request_ref,
            )
            if receipt.result_ref:
                replay = UUID(receipt.result_ref.id), receipt.request_ref
            else:
                updated = await service.authorize(db, account, scope, True)
                await lock_position(db, scope)
                latest = await history.current(db, scope)
                if latest.active_input_id is not None:
                    raise RequestError(409, "interaction_busy", "正在处理上一条，草稿已保留。")
                if (
                    await next_position(db, scope) != (sequence, epoch)
                    or updated.adoption_ref != adoption.adoption_ref
                ):
                    raise RequestError(409, "revision_conflict", "学习空间已更新，请再发送一次。")
                await service.append(db, scope, principal, response.request_ref, prepared)
                leaf = latest.current_activity
                if practice:
                    await self._save_submission(db, scope, principal, response, practice, latest)
                await store_position(
                    db,
                    scope,
                    leaf.activity_ref.activity_id if leaf else None,
                    sequence - 1 if practice else sequence,
                    epoch + 1,
                )
                await self._occupy(db, scope, response.input_id)
                work = await store.accept(
                    db,
                    self.registry,
                    _caller(principal, scope, "accept"),
                    entry_name=entry,
                    scope_kind=SCOPE,
                    scope_id=scope,
                    acceptance_key=str(response.request_ref),
                    input_ref=identity,
                    seconds=300,
                    basis_refs=[adoption.adoption_ref],
                    ai_config_ref=response.execution_ref,
                )
                await ai_store.pin(db, work, config)
                await service.receipts.complete_request(
                    db, receipt, ref("event", accepted.event_id)
                )
                replay = None
        return response if replay is None else await self._read_acceptance(scope, *replay)

    async def prepare_detection(
        self,
        account: AccountView,
        scope: UUID,
        command: PrepareDetectionCommand,
    ) -> LearningInputAcceptance:
        return await self.accept(
            account,
            scope,
            LearningInputCommand(
                request_id=command.request_id,
                input=StudentInput(
                    text="按当前学习目标准备检测。", attachment_refs=[], explicit_refs=[]
                ),
            ),
            preparing_detection=True,
        )

    async def submit_answer(
        self, account: AccountView, scope: UUID, command: AnswerCommand
    ) -> AnswerReceipt:
        accepted = await self.accept(
            account,
            scope,
            LearningInputCommand(
                request_id=command.request_id,
                input=StudentInput(text=command.answer.text, attachment_refs=[], explicit_refs=[]),
            ),
            practice=command,
        )
        return AnswerReceipt(
            request_ref=accepted.request_ref,
            submission_ref=ref("submission", command.submission_id),
            event_ref=uuid5(accepted.input_id, "answer-submitted"),
            round_state="closed" if command.round_ref else None,
            feedback_runtime_ref=accepted.execution_ref,
        )

    async def _save_submission(
        self,
        db: AsyncConnection,
        scope: UUID,
        principal: UUID,
        acceptance: LearningInputAcceptance,
        practice: AnswerCommand,
        current: CurrentConversation,
    ) -> None:
        leaf = current.current_activity
        if leaf is None or leaf.activity_ref != practice.activity_ref or leaf.run_state != "active":
            if (
                practice.round_ref
                and current.current_round
                and current.current_round.state == "closed"
            ):
                raise RequestError(409, "round_closed", "当前检测轮已经结束。")
            raise RequestError(409, "revision_conflict", "作答所属活动已变动。")
        if practice.task_use_ref.owner != "interaction" or practice.task_use_ref.type != "task_use":
            raise RequestError(400, "invalid_reference", "请选择本次活动中的练习。")
        try:
            use_id = UUID(practice.task_use_ref.id)
        except ValueError as error:
            raise RequestError(400, "invalid_reference", "练习编号无效。") from error
        opened = current.current_round if practice.round_ref else None
        if practice.round_ref:
            if opened is None or opened.state != "open":
                raise RequestError(409, "round_closed", "当前检测轮已经结束。")
            if (
                opened.round_ref != practice.round_ref
                or opened.round_ref.revision != practice.expected_round_revision
                or opened.task_use_ref != practice.task_use_ref
            ):
                raise RequestError(409, "revision_conflict", "检测题目或轮次已变化。")
        elif practice.expected_round_revision is not None:
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
            raise RequestError(404, "not_found", "找不到此练习。")
        if await db.scalar(
            text("SELECT 1 FROM interaction.submissions WHERE submission_id=:id"),
            {"id": practice.submission_id},
        ):
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
                activity_ref=ref(
                    "activity", leaf.activity_ref.activity_id, leaf.activity_ref.revision
                ),
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
            events.append(closure)
        events.append(replace(event, event_id=event_id))
        if opened:
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
        await self.conversation.append(db, scope, principal, acceptance.request_ref, events)

    async def _read_acceptance(
        self, scope: UUID, event: UUID, request: UUID
    ) -> LearningInputAcceptance:
        return LearningInputAcceptance.model_validate_json(
            await self._read_part(scope, event, request, facts.ACCEPTED, "/acceptance")
        )

    async def receipt(
        self, principal: UUID, _session: UUID, query: ReceiptQuery
    ) -> ReceiptView[LearningTurnResult]:
        async with self.engine.connect() as db:
            saved = await self.conversation.receipts.find_completed_request(
                db, principal, query.action, query.resource_id, query.request_id
            )
        if saved is None or saved.result_ref is None:
            return ReceiptView[LearningTurnResult](receipt_state="not_found")
        accepted = await self._read_acceptance(
            query.resource_id, UUID(saved.result_ref.id), saved.request_ref
        )
        async with self.engine.connect() as db:
            state = await store.load(db, accepted.execution_ref)
            finished = await db.scalar(
                text(
                    "SELECT source_event_id FROM interaction.input_results "
                    "WHERE input_id=:id AND step_key=:step"
                ),
                {"id": accepted.input_id, "step": await self._reply_step(db, state)},
            )
        turn = (
            LearningTurnResult.model_validate_json(
                await self._read_part(
                    query.resource_id, finished, saved.request_ref, facts.COMPLETED, "/turn_result"
                )
            )
            if finished is not None
            else None
        )
        return ReceiptView[LearningTurnResult](
            receipt_state="completed" if turn else "accepted",
            receipt_ref=accepted.request_ref,
            execution_ref=accepted.execution_ref,
            execution_state=state.state,
            business_state=turn.outcome if turn else None,
            result=turn,
        )

    async def retry(
        self, account: AccountView, scope: UUID, command: RetryLearningWork
    ) -> LearningInputAcceptance:
        async with self.engine.begin() as db:
            await self.conversation.authorize(db, account, scope, True)
            try:
                current = await store.load(db, command.execution_ref)
            except NoResultFound as error:
                raise RequestError(404, "not_found", "找不到这次交流。") from error
            if current.scope_id != scope or current.entry_ref not in {
                HANDLE_INPUT,
                PREPARE_DETECTION,
            }:
                raise RequestError(404, "not_found", "找不到这次交流。")
            authorization = await store.authorization(db, current.execution_id)
            if authorization.initiator_ref.id != str(account.account_id):
                raise RequestError(404, "not_found", "找不到这次交流。")
            try:
                saved = await commands.retry(
                    db,
                    self.registry,
                    _caller(account.account_id, scope, "retry"),
                    current.execution_id,
                    request_id=command.request_id,
                    seconds=300,
                )
            except ValueError as error:
                raise RequestError(409, "blocked", "这次交流当前不能重试。") from error
            return LearningInputAcceptance(
                request_ref=UUID(saved.acceptance_key),
                execution_ref=saved.execution_id,
                input_id=UUID(saved.input_ref.id),
            )

    async def stop(
        self, account: AccountView, scope: UUID, command: StopReply
    ) -> ActivityControlReceipt:
        service = self.conversation
        async with self.engine.connect() as db:
            await service.authorize(db, account, scope, False)
            original = (
                await db.execute(
                    text(
                        "SELECT request_id,kind FROM interaction.inputs "
                        "WHERE scope_id=:scope AND input_id=:input "
                        "AND kind IN ('message','answer','activity_control')"
                    ),
                    {"scope": scope, "input": command.target_input_id},
                )
            ).one_or_none()
            if original is None:
                raise RequestError(404, "not_found", "找不到这次交流。")
            original_receipt = await service.receipts.find_completed_request(
                db,
                account.account_id,
                {"answer": SUBMIT_ANSWER, "activity_control": PREPARE_DETECTION}.get(
                    original.kind, HANDLE_INPUT
                ),
                scope,
                original.request_id,
            )
        if original_receipt is None or original_receipt.result_ref is None:
            raise RequestError(404, "not_found", "找不到这次交流。")
        accepted = await self._read_acceptance(
            scope, UUID(original_receipt.result_ref.id), original_receipt.request_ref
        )
        async with self.engine.begin() as db:
            receipt = await service.receipts.claim_request(
                db,
                principal_id=str(account.account_id),
                action=CONTROL_ACTIVITY,
                scope_id=str(scope),
                request_id=command.request_id,
                normalized_input=command.model_dump(mode="json", exclude={"request_id"}),
            )
            if receipt.result_ref is None:
                adoption = await service.authorize(db, account, scope, True)
                await lock_position(db, scope)
                stopped = await commands.cancel(
                    db,
                    self.registry,
                    _caller(account.account_id, scope, "cancel"),
                    accepted.execution_ref,
                    request_id=command.request_id,
                )
                current = await history.current(db, scope)
                outcome = ActivityControlResult(
                    current=current,
                    outcome="stopped" if stopped.state == "cancelled" else "already_committed",
                    committed_refs=[stopped.result_ref] if stopped.result_ref else [],
                )
                now = datetime.now(UTC)
                _, epoch = await next_position(db, scope)
                identity = ref("input", uuid4())
                original = facts.InputFact(
                    input_id=UUID(identity.id),
                    scope_id=scope,
                    request_id=command.request_id,
                    kind="stop",
                    input=command.model_dump(mode="json"),
                    turn_epoch=epoch,
                    accepted_at=now,
                )
                result = self._result(original.input_id, "control", "completed", [], None)
                result_ref = ref("input_result", result.result_id)
                completed = draft(
                    scope,
                    facts.COMPLETED,
                    result_ref,
                    facts.InputCompleted(
                        records=[facts.record(facts.RESULT, result.result_id, result)],
                        input_ref=identity,
                        result_ref=result_ref,
                        control_result=outcome,
                    ),
                    command.request_id,
                )
                await service.append(
                    db,
                    scope,
                    account.account_id,
                    receipt.request_ref,
                    [
                        draft(
                            scope,
                            facts.ACCEPTED,
                            identity,
                            facts.InputAccepted(
                                records=[facts.record(facts.INPUT, original.input_id, original)],
                                input_ref=identity,
                                adoption_ref=adoption.adoption_ref,
                            ),
                            command.request_id,
                        ),
                        completed,
                    ],
                )
                await service.receipts.complete_request(
                    db, receipt, ref("event", completed.event_id)
                )
                return ActivityControlReceipt(request_ref=receipt.request_ref, result=outcome)
        assert receipt.result_ref is not None
        data = await self._read_part(
            scope,
            UUID(receipt.result_ref.id),
            receipt.request_ref,
            facts.COMPLETED,
            "/control_result",
        )
        return ActivityControlReceipt(
            request_ref=receipt.request_ref, result=ActivityControlResult.model_validate_json(data)
        )

    async def context(
        self, run: RunInput, question: ReadQuestion | None = None, *, post_close: bool = False
    ) -> str:
        """只从固定输入与当前活动取材。"""
        async with self.engine.begin() as db:
            work = await store.active(db, self.registry, run, "step")
            submission = await self._answer_row(db, UUID(work.input_ref.id))
            if submission is not None:
                if submission.round_id:
                    position = await history.current(db, work.scope_id)
                    fixed_round = position.current_round
                    if (
                        fixed_round
                        and fixed_round.can_continue
                        and fixed_round.round_ref.id == str(submission.round_id)
                    ):
                        return ACKNOWLEDGE_ANSWER
                related = await question(db, submission.instance_ref) if question else None
                fixed = related.model_dump(mode="json") if related else None
                return (
                    canonical_json({"mode": "answer_feedback", "question": fixed})
                    + "\n本轮输入（JSON）\n"
                    + canonical_json(submission.answer)
                )
            raw = await db.scalar(
                text("SELECT input FROM interaction.inputs WHERE input_id=:id"),
                {"id": UUID(work.input_ref.id)},
            )
            current = await history.current(db, work.scope_id)
            assessment = current.current_round
            if post_close and (assessment is None or assessment.state != "closed"):
                raise RuntimeError("Post-round help requires a closed round")
            if assessment and not post_close:
                return (
                    canonical_json({"mode": "detection_message", "round_state": assessment.state})
                    + "\n本轮输入（JSON）\n"
                    + canonical_json(raw)
                )
            fixed_question = None
            if post_close and assessment and question:
                source = await db.scalar(
                    text(
                        "SELECT instance_ref FROM interaction.task_uses "
                        "WHERE scope_id=:scope AND task_use_id=:id"
                    ),
                    {"scope": work.scope_id, "id": UUID(assessment.task_use_ref.id)},
                )
                if source is not None:
                    fixed_question = await question(db, Ref.model_validate(source))
            grant = await store.authorization(db, work.execution_id)
            leaf = current.current_activity
            active = (
                await history.activity_at(db, work.scope_id, leaf.activity_ref.activity_id)
                if leaf
                else None
            )
            memories = (
                await memory_facts.read(db, work.scope_id, leaf.activity_ref.activity_id)
                if leaf
                else []
            )
            covered_through = next(
                (item.basis_message_seq for item in memories if item.kind == "summary"), 0
            )
            # 摘要未保存时，继续读取本轮能放入预算的原消息。
            recent = await db.execute(
                text(
                    "SELECT m.message_id,m.role,m.parts FROM interaction.messages m "
                    "LEFT JOIN interaction.message_assignments a ON a.message_id=m.message_id "
                    "WHERE m.scope_id=:scope AND m.source_input_ref IS DISTINCT FROM :input "
                    "AND a.activity_id IS NOT DISTINCT FROM CAST(:activity AS uuid) "
                    "AND m.role IN ('student','assistant') AND m.message_seq>:covered "
                    "ORDER BY m.message_seq DESC LIMIT :limit"
                ),
                {
                    "scope": work.scope_id,
                    "input": UUID(work.input_ref.id),
                    "activity": leaf.activity_ref.activity_id if leaf else None,
                    "covered": covered_through,
                    "limit": memory_facts.HISTORY_WINDOW,
                },
            )
            history_text: list[dict[str, JsonValue]] = []
            message_refs: list[Ref] = []
            remaining = 32 * 1024
            for item in recent.mappings():
                message: dict[str, JsonValue] = {"role": item["role"], "parts": item["parts"]}
                remaining -= len(canonical_json(message).encode("utf-8"))
                if remaining < 0:
                    break
                history_text.append(message)
                message_refs.append(ref("message", item["message_id"]))
        source = StudentInput.model_validate_json(canonical_json(raw))
        contexts: list[dict[str, JsonValue]] = []
        quoted: list[dict[str, JsonValue]] = []
        adoption_id = UUID(grant.basis_refs[0].id)
        for reference in source.explicit_refs:
            parts = await self.read_chapter(work.scope_id, adoption_id, reference)
            if len(canonical_json(parts).encode()) <= 16 * 1024:
                quoted.append(
                    {
                        "ref": reference.model_dump(mode="json"),
                        "parts": [item for item in parts],
                    }
                )
            else:
                quoted.append(
                    {
                        "ref": reference.model_dump(mode="json"),
                        "omission": "章节超出本轮取材范围，请学生指出具体段落。",
                    }
                )
        if active is None or active.identity.type != "detection" or post_close:
            adoption = active.identity.adoption_ref if active else UUID(grant.basis_refs[0].id)
            kinds: tuple[ActivityType, ...] = ("explanation", "question_answer")
            for kind in kinds:
                positions: list[history.ActivityState | None] = [None]
                if active and active.identity.type == kind:
                    positions.append(active)
                for position in positions:
                    config, course = await self.activity_config(
                        work.scope_id,
                        adoption,
                        kind,
                        position.identity.config_ref if position else None,
                    )
                    if config is not None and not config.gaps:
                        chosen = await self._prepare_lesson(
                            run,
                            work,
                            adoption,
                            config,
                            course,
                            position,
                            [*message_refs, *source.explicit_refs],
                            [value.identity for value in memories],
                        )
                        if chosen is not None:
                            contexts.append(chosen)
        return (
            canonical_json(
                {
                    "mode": "post_detection_help" if post_close else "conversation",
                    "question": fixed_question.model_dump(mode="json") if fixed_question else None,
                    "quoted_material": quoted,
                    "memory": [value.content for value in memories],
                    "activity": current.current_activity.model_dump(mode="json")
                    if current.current_activity
                    else None,
                    "recent": list(reversed(history_text)),
                    "teaching_contexts": contexts,
                }
            )
            + "\n本轮输入（JSON）\n"
            + canonical_json(raw)
        )

    async def _prepare_lesson(
        self,
        run: RunInput,
        work: Execution,
        adoption: UUID,
        config: ConfigView,
        course: CourseSnapshot,
        activity: history.ActivityState | None,
        messages: list[Ref],
        memory_refs: list[Ref],
    ) -> dict[str, JsonValue] | None:
        definition = config.definition
        kind = definition.activity_type
        if kind != "explanation" and kind != "question_answer":
            raise ValueError("Expected a teaching activity configuration")
        node = (
            next(
                item
                for item in definition.blueprint.nodes
                if item.node_id == activity.position.node_id
            )
            if activity
            else entry_node(definition.blueprint)
        )
        if node is None:
            return None
        binding = effective_binding(definition, node.node_id)
        rules = [item for item in definition.rules if UUID(item.ref.id) in binding.rule_ids]
        strategies = [
            item for item in definition.strategies if UUID(item.ref.id) in binding.strategy_ids
        ]
        transitions = [
            edge
            for edge in definition.blueprint.transitions
            if edge.source_node_id == node.node_id and edge.when in {"on_input", "after_reply"}
        ]
        position = "current" if activity else "entry"
        bundle_id = uuid5(NAMESPACE_URL, f"{work.execution_id}:{kind}:{position}")
        current_ref = (
            ref("activity", activity.identity.activity_id, activity.position.revision)
            if activity
            else None
        )
        source_refs = [
            work.input_ref,
            config.config_ref,
            Ref(owner="product", type="space_adoption", id=str(adoption)),
            *messages,
            *(rule.ref for rule in rules),
            *(strategy.ref for strategy in strategies),
        ]
        row = facts.ContextFact(
            bundle_id=bundle_id,
            scope_id=work.scope_id,
            run_ref=work.execution_id,
            source_ref=work.input_ref,
            purpose=kind,
            activity_revision_ref=current_ref,
            adoption_ref=adoption,
            config_ref=UUID(config.config_ref.id),
            materials=[{"ref": value.model_dump(mode="json")} for value in source_refs],
            memory_refs=memory_refs,
            publication_refs=[],
            omissions=[],
            created_at=datetime.now(UTC),
        )
        async with self.engine.begin() as db:
            await store.active(db, self.registry, run, "step")
            existing = await db.scalar(
                text("SELECT bundle_id FROM interaction.context_bundles WHERE bundle_id=:id"),
                {"id": bundle_id},
            )
            if existing is None:
                authorization = await store.authorization(db, work.execution_id)
                request_id = await db.scalar(
                    text("SELECT request_id FROM interaction.inputs WHERE input_id=:id"),
                    {"id": UUID(work.input_ref.id)},
                )
                if not isinstance(request_id, str):
                    raise RuntimeError("Context must reference an accepted input")
                owner = ref("context_bundle", bundle_id)
                await self.conversation.append(
                    db,
                    work.scope_id,
                    UUID(authorization.initiator_ref.id),
                    UUID(work.acceptance_key),
                    [
                        draft(
                            work.scope_id,
                            facts.CONTEXT_PREPARED,
                            owner,
                            facts.ContextPrepared(
                                subject_ref=owner,
                                records=[facts.record(facts.CONTEXT, bundle_id, row)],
                            ),
                            request_id,
                        )
                    ],
                )
        return {
            "context_ref": str(bundle_id),
            "activity_type": kind,
            "position": position,
            "node": node.model_dump(mode="json"),
            "rules": [item.model_dump(mode="json") for item in rules],
            "strategies": [item.model_dump(mode="json") for item in strategies],
            "transitions": [item.model_dump(mode="json") for item in transitions],
            "course": {
                "textbook": course.textbook_title,
                "target": course.target_title,
                "items": [
                    {"title": item.title, "task_conditions": item.task_conditions.description}
                    for item in course.items
                ],
                "question_tasks": [
                    task.model_dump(mode="json") for task in teaching_options(course)
                ],
            },
        }

    async def request_question(
        self,
        run: RunInput,
        question: TeachingQuestion,
        waits: Waits,
        domain_for: Callable[[AsyncConnection, UUID], Awaitable[UUID]],
    ) -> WaitCall | None:
        async with self.engine.connect() as db:
            work = await store.load(db, run.execution_id)
            active = (await history.current(db, work.scope_id)).current_activity
            if active is None or active.type not in {"explanation", "question_answer"}:
                return None
            state = await history.activity_at(db, work.scope_id, active.activity_ref.activity_id)
        config, course = await self.activity_config(
            work.scope_id, state.identity.adoption_ref, active.type, state.identity.config_ref
        )
        if config is None or not any(
            node.node_id == active.node_id and "reply" in node.allowed_actions
            for node in config.definition.blueprint.nodes
        ):
            return None
        async with self.engine.begin() as db:
            work = await store.active(db, self.registry, run, "step")
            leaf = (await history.current(db, work.scope_id)).current_activity
            if leaf is None or active.activity_ref != leaf.activity_ref:
                return None
            principal = UUID((await store.authorization(db, run.execution_id)).initiator_ref.id)
            request_id = await db.scalar(
                text("SELECT request_id FROM interaction.inputs WHERE input_id=:id"),
                {"id": UUID(work.input_ref.id)},
            )
            if not isinstance(request_id, str):
                raise ValueError("Question supply requires its original input")
            saved = await wait_for_question(
                db,
                self.conversation,
                waits,
                run,
                work,
                leaf,
                course,
                question,
                domain_for,
                principal,
                request_id,
            )
            return WaitCall(run=run, wait_id=saved.wait_id) if saved else None

    async def finish(
        self,
        run: RunInput,
        candidate: ReplyCandidate,
        candidate_id: UUID,
        card: TeachingCard | None = None,
        *,
        post_close: bool = False,
    ) -> None:
        config = None
        parent_config = None
        bundle = None
        async with self.engine.connect() as db:
            original = await store.load(db, run.execution_id)
            grant = await store.authorization(db, run.execution_id)
            current = await history.current(db, original.scope_id)
            leaf = current.current_activity
            requested = candidate.teaching
            if requested and candidate.intent in {"explanation", "question_answer"}:
                position = (
                    "current"
                    if leaf and leaf.type == candidate.intent and requested.placement == "continue"
                    else "entry"
                )
                context_id = uuid5(
                    NAMESPACE_URL, f"{run.execution_id}:{candidate.intent}:{position}"
                )
                raw = await db.scalar(
                    text(
                        "SELECT to_jsonb(c)-'source_event_id' FROM interaction.context_bundles c "
                        "WHERE bundle_id=:id AND run_ref=:run"
                    ),
                    {"id": context_id, "run": run.execution_id},
                )
                if raw is not None:
                    bundle = facts.ContextFact.model_validate_json(canonical_json(raw))
            parent = (
                await history.activity_at(db, original.scope_id, leaf.activity_ref.activity_id)
                if leaf and (leaf.type in {"explanation", "question_answer"} or post_close)
                else None
            )
        teaching_intent = ("explanation", "question_answer")
        teaching = candidate.intent in teaching_intent or (
            parent is not None and candidate.intent != "learning"
        )
        if bundle is not None:
            config, _course = await self.activity_config(
                original.scope_id, bundle.adoption_ref, bundle.purpose, bundle.config_ref
            )
            if parent and bundle.activity_revision_ref is None:
                parent_config, _course = await self.activity_config(
                    original.scope_id,
                    parent.identity.adoption_ref,
                    parent.identity.type,
                    parent.identity.config_ref,
                )
        elif candidate.intent == "free_chat" and leaf is None:
            config, _course = await self.activity_config(
                original.scope_id, UUID(grant.basis_refs[0].id), "free_chat", None
            )
        async with self.engine.begin() as db:
            saved = await store.lock_owned(db, self.registry, run.execution_id)
            if saved.state == "completed":
                return
            work = await store.active(db, self.registry, run, "finish")
            practice = await self._answer_row(db, UUID(work.input_ref.id))
            position = await history.current(db, work.scope_id)
            if practice is not None:
                if candidate.intent == "feedback" and candidate.verdict is not None:
                    await self._save_feedback(db, work, candidate, candidate_id, practice)
                    outcome, reply = "completed", candidate.wording
                else:
                    outcome, reply = "blocked", "作答已保存，暂时无法给出本题反馈。"
            elif position.current_round and (
                not post_close
                or position.current_round.state != "closed"
                or requested is None
                or requested.placement != "child"
                or candidate.intent not in teaching_intent
            ):
                outcome, reply = "needs_input", "你可以提交本题。需要讲解或提示时，可以直接提出。"
            elif candidate.question and card is None:
                outcome, reply = "blocked", "暂时没有准备好符合要求的题，可以继续当前内容。"
            elif teaching:
                outcome, reply = await self._run_teaching(
                    db, work, candidate, config, parent_config, bundle, candidate_id
                )
            else:
                outcome, reply = await self._interpret(db, work, candidate, config)
            if card and outcome == "completed":
                reply = (
                    "可以先试着完成这道练习。"
                    if card.part.purpose == "practice"
                    else "我们看这道例题。"
                )
            result = await self._save_result(
                db,
                work,
                outcome,
                reply,
                None,
                card if outcome == "completed" else None,
                teaching=(
                    outcome == "completed"
                    and practice is None
                    and candidate.intent in teaching_intent
                    and candidate.question is None
                ),
                memory=candidate.memory if outcome == "completed" and practice is None else None,
            )
            await commands.complete(db, self.registry, run, result)
            await self._occupy(db, work.scope_id, None)

    @staticmethod
    async def _answer_row(db: AsyncConnection, source: UUID) -> AnswerContext | None:
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

    async def acknowledge_answer(self, run: RunInput) -> None:
        async with self.engine.begin() as db:
            existing = await store.lock_owned(db, self.registry, run.execution_id)
            if existing.state == "completed":
                return
            work = await store.active(db, self.registry, run, "finish")
            answer = await self._answer_row(db, UUID(work.input_ref.id))
            if answer is None or answer.round_id is None:
                raise ValueError("An accepted detection answer is required")
            result = await self._save_result(
                db, work, "completed", "作答已保存，可以继续下一题。", None
            )
            await commands.complete(db, self.registry, run, result)
            await self._occupy(db, work.scope_id, None)

    async def _save_feedback(
        self,
        db: AsyncConnection,
        work: Execution,
        candidate: ReplyCandidate,
        candidate_id: UUID,
        practice: AnswerContext,
    ) -> None:
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
        await self.conversation.append(
            db,
            work.scope_id,
            principal,
            UUID(work.acceptance_key),
            [
                replace(
                    event, subject_refs=(Ref(owner="ai", type="candidate", id=str(candidate_id)),)
                ),
            ],
        )

    async def _run_teaching(
        self,
        db: AsyncConnection,
        work: Execution,
        candidate: ReplyCandidate,
        config: ConfigView | None,
        parent_config: ConfigView | None,
        bundle: facts.ContextFact | None,
        candidate_id: UUID,
    ) -> tuple[TurnOutcome, str]:
        if config is None or bundle is None or bundle.purpose != candidate.intent:
            return "needs_input", "你想继续当前内容，还是插入一个新问题？"
        scope, identity = work.scope_id, UUID(work.input_ref.id)
        current = await history.current(db, scope)
        leaf = current.current_activity
        node = (
            next(item for item in config.definition.blueprint.nodes if item.node_id == leaf.node_id)
            if bundle.activity_revision_ref and leaf
            else entry_node(config.definition.blueprint)
        )
        if node is None:
            return "blocked", "当前讲解缺少可用的开始节点。"
        item = (
            await db.execute(
                text(
                    "SELECT input,source_event_id,request_id FROM interaction.inputs "
                    "WHERE scope_id=:scope AND input_id=:id"
                ),
                {"scope": scope, "id": identity},
            )
        ).one()
        source = StudentInput.model_validate_json(canonical_json(item.input))
        original_text = source.text or ""
        placement = candidate.teaching.placement if candidate.teaching else "continue"
        quote = candidate.teaching.placement_quote if candidate.teaching else None
        node_actions = None
        if parent_config and leaf:
            parent_node = next(
                part
                for part in parent_config.definition.blueprint.nodes
                if part.node_id == leaf.node_id
            )
            node_actions = parent_node.allowed_actions
        placed = (
            placement == "continue"
            if bundle.activity_revision_ref is not None or node_actions is None
            else (
                placement in {"child", "new_topic"}
                and quote is not None
                and quote in original_text
                and ("start_child" if placement == "child" else "switch") in node_actions
            )
        )
        choice = (
            decide(config.definition, node, candidate.teaching, original_text, {})
            if candidate.teaching and placed
            else TeachingDecision("clarify", reason="activity_placement_unavailable")
        )
        authority = await store.authorization(db, work.execution_id)
        principal, request = UUID(authority.initiator_ref.id), UUID(work.acceptance_key)
        applied: Ref | None = bundle.activity_revision_ref
        if choice.action == "reply":
            applied = await self._apply_lesson(
                db,
                work,
                scope,
                principal,
                candidate,
                config,
                bundle,
                node,
                choice,
                item.source_event_id,
                item.request_id,
                placement,
            )
        decision_id = uuid4()
        owner = ref("decision", decision_id)
        saved = facts.DecisionFact(
            decision_id=decision_id,
            scope_id=scope,
            input_ref=identity,
            source_trigger_ref=None,
            activity_revision_ref=bundle.activity_revision_ref,
            context_bundle_id=bundle.bundle_id,
            ai_candidate_ref=Ref(owner="ai", type="candidate", id=str(candidate_id)),
            proposal=candidate.model_dump(mode="json"),
            validation={"passed": choice.reason is None, "reason": choice.reason},
            accepted_action={
                "action": choice.action,
                "placement": placement,
                "transition_id": choice.transition.transition_id if choice.transition else None,
                "activity_revision_ref": applied.model_dump(mode="json") if applied else None,
            },
            created_at=datetime.now(UTC),
        )
        await self.conversation.append(
            db,
            scope,
            principal,
            request,
            [
                draft(
                    scope,
                    facts.DECISION_RECORDED,
                    owner,
                    facts.DecisionRecorded(
                        subject_ref=owner,
                        outcome="allowed"
                        if choice.action == "reply"
                        else "clarify"
                        if choice.action == "clarify"
                        else "denied",
                        reason_code=choice.reason,
                        records=[facts.record(facts.DECISION, decision_id, saved)],
                    ),
                    item.request_id,
                )
            ],
        )
        if choice.action == "reply":
            return "completed", candidate.wording
        if choice.action == "clarify":
            return "needs_input", node.fallback.explanation if choice.reason else candidate.wording
        return "blocked", node.fallback.explanation

    async def _apply_lesson(
        self,
        db: AsyncConnection,
        work: Execution,
        scope: UUID,
        principal: UUID,
        candidate: ReplyCandidate,
        config: ConfigView,
        bundle: facts.ContextFact,
        node: BlueprintNode,
        choice: TeachingDecision,
        trigger: UUID,
        request_id: str,
        placement: Literal["continue", "child", "new_topic"],
    ) -> Ref:
        request = UUID(work.acceptance_key)
        identity = UUID(work.input_ref.id)
        current = await history.current(db, scope)
        leaf = current.current_activity
        if bundle.activity_revision_ref is None:
            parent_id = leaf.activity_ref.activity_id if leaf and placement == "child" else None
            if leaf is not None and parent_id is None:
                path = await history.lineage(db, scope, leaf.activity_ref.activity_id)
                completed = leaf.type == "free_chat" and leaf.parent_id is None
                if not completed and placement != "new_topic":
                    raise ValueError("Only a verified topic change can suspend an active lesson")
                now = datetime.now(UTC)
                changes = [
                    activity_change(
                        state.identity,
                        revise(
                            state.position,
                            "completed" if completed else "paused",
                            "end" if completed else state.position.node_id,
                            "change_topic",
                            now,
                            input_id=identity,
                        ),
                        request_id,
                    )
                    for state in path
                ]
                seq, epoch = await next_position(db, scope)
                await self.conversation.append(
                    db,
                    scope,
                    principal,
                    request,
                    [
                        *changes,
                        *notice_events(
                            scope,
                            leaf.activity_ref.activity_id,
                            uuid4(),
                            seq,
                            "自由交谈已结束。" if completed else "已暂停「" + leaf.name + "」。",
                            now,
                            input_id=identity,
                            request=request_id,
                        ),
                    ],
                )
                await store_position(db, scope, None, seq, epoch)
            adoption_ref = Ref(owner="product", type="space_adoption", id=str(bundle.adoption_ref))
            started = await self.conversation.begin(
                db,
                scope,
                principal,
                adoption_ref,
                config.config_ref,
                config.definition,
                bundle.purpose,
                candidate.topic,
                trigger,
                parent_id=parent_id,
                input_id=identity,
                initial_node=node.node_id,
                request_ref=request,
            )
            leaf_id = started.activity_id
        else:
            leaf_id = UUID(bundle.activity_revision_ref.id)
            if (
                leaf is None
                or ref("activity", leaf.activity_ref.activity_id, leaf.activity_ref.revision)
                != bundle.activity_revision_ref
            ):
                raise ValueError("The lesson changed before its candidate was accepted")
        state = await history.activity_at(db, scope, leaf_id)
        if choice.transition is None:
            return ref("activity", leaf_id, state.position.revision)
        target = choice.transition.target_node_id
        revised = revise(
            state.position,
            "completed" if target == "end" else "active",
            target,
            choice.transition.transition_id,
            datetime.now(UTC),
            input_id=identity,
        )
        await self.conversation.append(
            db, scope, principal, request, [activity_change(state.identity, revised, request_id)]
        )
        return ref("activity", leaf_id, revised.revision)

    async def _interpret(
        self,
        db: AsyncConnection,
        work: Execution,
        candidate: ReplyCandidate,
        config: ConfigView | None,
    ) -> tuple[TurnOutcome, str]:
        if candidate.intent == "clarify":
            return "needs_input", candidate.wording
        if candidate.intent == "learning":
            return "blocked", "这个请求需要讲解、答疑或检测。当前还无法开展该活动。"
        current = await history.current(db, work.scope_id)
        if current.current_activity is not None:
            return "completed", candidate.wording
        if config is None or config.gaps:
            return "blocked", "这门课程暂未配置自由交谈，请联系管理员。"
        entry = entry_node(config.definition.blueprint)
        start = next(node for node in config.definition.blueprint.nodes if node.node_id == "start")
        if entry is None or "reply" not in entry.allowed_actions:
            return "blocked", start.fallback.explanation
        trigger = await db.scalar(
            text("SELECT source_event_id FROM interaction.inputs WHERE input_id=:id"),
            {"id": UUID(work.input_ref.id)},
        )
        if not isinstance(trigger, UUID):
            raise RuntimeError("Student input is missing its source event")
        grant = await store.authorization(db, work.execution_id)
        await self.conversation.begin(
            db,
            work.scope_id,
            UUID(grant.initiator_ref.id),
            grant.basis_refs[0],
            config.config_ref,
            config.definition,
            "free_chat",
            candidate.topic,
            trigger,
            parent_id=None,
            input_id=UUID(work.input_ref.id),
            initial_node=entry.node_id,
            request_ref=UUID(work.acceptance_key),
        )
        return "completed", candidate.wording

    async def _finalize(
        self, db: AsyncConnection, work: Execution, state: State, cause: Ref | None
    ) -> None:
        if state == "completed":
            return
        active = await history.current(db, work.scope_id)
        if active.active_input_id != UUID(work.input_ref.id):
            return
        if state == "cancelled":
            await self._save_result(db, work, "cancelled", None, None)
        else:
            await self._save_result(db, work, "failed", None, cause)
        await self._occupy(db, work.scope_id, None)

    async def _save_result(
        self,
        db: AsyncConnection,
        work: Execution,
        outcome: TurnOutcome,
        reply: str | None,
        error: Ref | None,
        card: TeachingCard | None = None,
        plan: DetectionPlanPart | None = None,
        *,
        teaching: bool = False,
        memory: memory_facts.Remember | None = None,
    ) -> Ref:
        scope, input_id = work.scope_id, UUID(work.input_ref.id)
        service = self.conversation
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
                    TextPart(part_id="text", type="text", text=reply),
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
            if teaching and saved_activity is not None:
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
                provided = await self._provided_help(db, work, message, request_id)
                if provided:
                    commands_to_save.append(provided)
                if memory is not None:
                    update = await self._working_memory(db, work, message, saved_activity, memory)
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
                adoption = saved_activity.identity.adoption_ref
                use = task_facts.TaskUseFact(
                    task_use_id=UUID(card.part.task_use_ref.id),
                    scope_id=scope,
                    activity_id=activity,
                    round_id=None,
                    plan_item_ref=None,
                    instance_ref=card.instance_ref,
                    statement=card.part.statement.model_dump(mode="json"),
                    adoption_ref=adoption,
                    purpose=card.part.purpose,
                    method_conditions={
                        "method_refs": [item.model_dump(mode="json") for item in card.method_refs]
                    },
                    prepared_at=message.committed_at,
                    provided_message_ref=message.message_id,
                )
                commands_to_save.append(
                    draft(
                        scope,
                        task_facts.PRESENTED,
                        card.part.task_use_ref,
                        task_facts.TaskUseCreated(
                            task_use_ref=card.part.task_use_ref,
                            activity_ref=ref("activity", activity, leaf.activity_ref.revision),
                            round_ref=None,
                            plan_ref=None,
                            adoption_ref=Ref(
                                owner="product", type="space_adoption", id=str(adoption)
                            ),
                            records=[facts.record(task_facts.TASK_USE, use.task_use_id, use)],
                        ),
                        request_id,
                    )
                )
            if activity is not None:
                original = await db.scalar(
                    text(
                        "SELECT to_jsonb(m)-'source_event_id' FROM interaction.messages m "
                        "WHERE scope_id=:scope AND source_input_ref=:input AND role='student'"
                    ),
                    {"scope": scope, "input": input_id},
                )
                if original is None and not await self._answer_row(db, input_id):
                    raise RuntimeError("Accepted student input is missing its message")
                if original is not None:
                    origin = facts.MessageFact.model_validate_json(canonical_json(original))
                    commands_to_save.append(assign_message(origin, activity, request_id))
                commands_to_save.append(assign_message(message, activity, request_id))
            messages.append(message.message_id)
            next_leaf = activity
            if leaf is not None and leaf.run_state == "completed":
                sequence += 1
                notice_id = uuid4()
                path = await history.lineage(db, scope, leaf.activity_ref.activity_id)
                returning = return_point(path)
                ending = "已结束「" + leaf.name + "」。"
                next_leaf = None
                if returning is not None:
                    parent, node = returning
                    restored = revise(
                        parent.position,
                        "active",
                        node,
                        "return_parent",
                        datetime.now(UTC),
                        input_id=input_id,
                    )
                    commands_to_save.append(activity_change(parent.identity, restored, request_id))
                    ending = "回到「" + parent.identity.name + "」。"
                    next_leaf = parent.identity.activity_id
                commands_to_save.extend(
                    notice_events(
                        scope,
                        leaf.activity_ref.activity_id,
                        notice_id,
                        sequence,
                        ending,
                        datetime.now(UTC),
                        input_id=input_id,
                        request=request_id,
                    )
                )
                messages.append(notice_id)
            if card:
                commands_to_save = [
                    replace(item, causation_event_id=card.supply_event_id)
                    if item.event_type == task_facts.PRESENTED
                    else item
                    for item in commands_to_save
                ]
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
        result = self._result(input_id, await self._reply_step(db, work), outcome, messages, error)
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

    @staticmethod
    async def _working_memory(
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

    @staticmethod
    async def _provided_help(
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

    async def save_plan_result(
        self,
        db: AsyncConnection,
        run: RunInput,
        work: Execution,
        wording: str,
        plan: DetectionPlanPart | None,
    ) -> None:
        result = await self._save_result(
            db, work, "completed" if plan else "blocked", wording, None, plan=plan
        )
        await commands.complete(db, self.registry, run, result)
        await self._occupy(db, work.scope_id, None)

    @staticmethod
    async def _reply_step(db: AsyncConnection, work: Execution) -> str:
        if work.active_attempt_id is None:
            return "reply"
        attempt = await store.attempt(db, work.active_attempt_id)
        return "reply" if attempt.attempt_no == 1 else f"reply:{attempt.attempt_no}"

    @staticmethod
    async def _occupy(db: AsyncConnection, scope: UUID, identity: UUID | None) -> None:
        await db.execute(
            text("UPDATE interaction.space_runtime SET active_input_id=:id WHERE scope_id=:scope"),
            {"scope": scope, "id": identity},
        )

    @staticmethod
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
