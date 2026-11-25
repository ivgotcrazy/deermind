"""Student requests, receipts and ownership of the active turn."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import partial
from hashlib import sha256
from uuid import UUID, uuid4, uuid5

from deermind.abstractions.ai.contracts import ExecutionConfig
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import Ref
from deermind.abstractions.executions import Authorization, Execution
from deermind.foundation.ai import store as ai_store
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.executions import commands, store
from deermind.foundation.system.executions.contracts import Caller, Entry, Registry
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.public.authentication import AccountView
from deermind.spaces.interaction import conversation_facts as facts
from deermind.spaces.interaction import (
    history,
)
from deermind.spaces.interaction.answer_feedback import (
    save_submission,
)
from deermind.spaces.interaction.conversation import (
    SCOPE,
    Conversation,
    draft,
    event_access,
    lock_position,
    message_event,
    next_position,
    ref,
    store_position,
)
from deermind.spaces.interaction.public import (
    CONTROL_ACTIVITY,
    HANDLE_INPUT,
    PREPARE_DETECTION,
    SUBMIT_ANSWER,
    ActivityControlReceipt,
    ActivityControlResult,
    AnswerCommand,
    AnswerReceipt,
    LearningInputAcceptance,
    LearningInputCommand,
    LearningTurnResult,
    PrepareDetectionCommand,
    RetryLearningWork,
    StopReply,
    StudentInput,
    TextPart,
)
from deermind.spaces.interaction.turn_result import finalize_turn, reply_step, set_active_input
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncConnection

WORKFLOW = "interaction.handle_input"
type SpaceAdoption = Callable[[AsyncConnection, UUID, bool], Awaitable[UUID]]


def _caller(principal: UUID, scope: UUID, action: str) -> Caller:
    return Caller(
        Ref(owner="product", type="account", id=str(principal)),
        "interaction",
        frozenset({(SCOPE, scope)}),
        frozenset({action}),
    )


class TurnRequests:
    """Accept inputs and control the execution that owns the learning space."""

    def __init__(
        self,
        conversation: Conversation,
        current_adoption: SpaceAdoption,
        attachments: FactAttachments,
        queue: str,
        config: ExecutionConfig | None,
    ) -> None:
        self.conversation = conversation
        self.engine = conversation.engine
        self.current_adoption = current_adoption
        self.attachments = attachments
        self.config = config
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
                    partial(finalize_turn, conversation),
                )
                for entry in (HANDLE_INPUT, PREPARE_DETECTION)
            ]
        )

    async def _lock(self, db: AsyncConnection, kind: str, scope: UUID) -> None:
        if kind != SCOPE:
            # 执行锁定只接受学习空间作用域。
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
            # 读取与取消不校验输入持有权。
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
                # 无进行中输入或采用依据已变，重试被拒绝。
                raise RequestError(409, "revision_conflict", "当前交流已变化，无法重试原请求。")
            await set_active_input(db, scope, input_id)
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
            # 输入已不持有空间，或采用依据与授权不符。
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
        self, account: AccountView, scope: UUID, command: LearningInputCommand
    ) -> LearningInputAcceptance:
        return await self._accept(account, scope, command)

    async def _accept(
        self,
        account: AccountView,
        scope: UUID,
        command: LearningInputCommand | AnswerCommand | PrepareDetectionCommand,
    ) -> LearningInputAcceptance:
        """Prepare material before locking, then recheck adoption and turn ownership."""
        entry = HANDLE_INPUT
        if isinstance(command, AnswerCommand):
            # 作答提交：动作记为提交答案，正文取自学生作答。
            action, kind = SUBMIT_ANSWER, "answer"
            content = StudentInput(text=command.answer.text, attachment_refs=[], explicit_refs=[])
            identity_input = command
        elif isinstance(command, PrepareDetectionCommand):
            # 准备检测：走检测入口，正文为系统占位文本。
            entry = PREPARE_DETECTION
            action, kind = entry, "activity_control"
            content = StudentInput(
                text="按当前学习目标准备检测。",
                attachment_refs=[],
                explicit_refs=[],
            )
            identity_input = content
        else:
            # 普通聊天消息。
            action, kind = entry, "message"
            content = command.input
            identity_input = content
        normalized: dict[str, JsonValue] = {
            "digest": sha256(
                canonical_json(identity_input.model_dump(mode="json")).encode()
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
            # 同请求已有完成记录，按幂等重放回执。
            assert saved.result_ref is not None
            return await self._read_acceptance(scope, UUID(saved.result_ref.id), saved.request_ref)
        if (
            isinstance(command, AnswerCommand)
            and command.round_ref
            and before.current_round
            and before.current_round.round_ref.id == command.round_ref.id
            and before.current_round.state == "closed"
        ):
            # 目标检测轮已闭环，不能再作答。
            raise RequestError(409, "round_closed", "当前检测轮已经结束。")
        if before.active_input_id is not None:
            # 空间尚有进行中输入，拒绝并发。
            raise RequestError(409, "interaction_busy", "正在处理上一条，草稿已保留。")
        if content.attachment_refs:
            # 本轮聊天不接收附件。
            raise RequestError(400, "invalid_reference", "当前聊天只接收文字和教材引用。")
        references = content.explicit_refs
        if references:
            # 显式引用必须落在当前采用快照的章节/内容范围内。
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
                # 一次只允许一条引用，且必须在可用清单内。
                raise RequestError(404, "not_found", "引用的教材内容不在当前采用范围内。")
        config = self.config
        if config is None:
            # 缺模型配置，无法启动执行。
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
            kind=kind,
            input=content.model_dump(mode="json"),
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
            parts=[TextPart(part_id="text", type="text", text=content.text or "")],
            source_input_ref=response.input_id,
            source_trigger_ref=None,
            committed_at=now,
        )
        prepared = await self.attachments.prepare(
            service.events,
            event_access(scope, principal),
            (accepted,)
            if isinstance(command, AnswerCommand)
            else (accepted, message_event(user_message, None, command.request_id)),  # 普通输入另落学生消息事件
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
                # 认领时发现已有完成回执，直接重放。
                replay = UUID(receipt.result_ref.id), receipt.request_ref
            else:
                updated = await service.authorize(db, account, scope, True)
                await lock_position(db, scope)
                latest = await history.current(db, scope)
                if latest.active_input_id is not None:
                    # 加锁后仍有进行中输入，视为并发冲突。
                    raise RequestError(409, "interaction_busy", "正在处理上一条，草稿已保留。")
                if (
                    await next_position(db, scope) != (sequence, epoch)
                    or updated.adoption_ref != adoption.adoption_ref
                ):
                    # 消息序号/轮次或采用依据在准备期间发生变化，乐观锁冲突。
                    raise RequestError(409, "revision_conflict", "学习空间已更新，请再发送一次。")
                await service.append(db, scope, principal, response.request_ref, prepared)
                leaf = latest.current_activity
                if isinstance(command, AnswerCommand):
                    # 作答输入额外落提交事实。
                    await save_submission(service, db, scope, principal, response, command, latest)
                await store_position(
                    db,
                    scope,
                    leaf.activity_ref.activity_id if leaf else None,
                    sequence - 1 if isinstance(command, AnswerCommand) else sequence,
                    epoch + 1,
                )
                await set_active_input(db, scope, response.input_id)
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
        return await self._accept(account, scope, command)

    async def submit_answer(
        self, account: AccountView, scope: UUID, command: AnswerCommand
    ) -> AnswerReceipt:
        accepted = await self._accept(account, scope, command)
        return AnswerReceipt(
            request_ref=accepted.request_ref,
            submission_ref=ref("submission", command.submission_id),
            event_ref=uuid5(accepted.input_id, "answer-submitted"),
            round_state="closed" if command.round_ref else None,
            feedback_runtime_ref=accepted.execution_ref,
        )

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
            # 无完成回执，按未找到返回。
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
                {"id": accepted.input_id, "step": await reply_step(db, state)},
            )
        turn = (
            LearningTurnResult.model_validate_json(
                await self._read_part(
                    query.resource_id, finished, saved.request_ref, facts.COMPLETED, "/turn_result"
                )
            )
            if finished is not None
            else None  # 尚无完成结果事件，回执停留在已接受状态
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
                # 执行记录不存在。
                raise RequestError(404, "not_found", "找不到这次交流。") from error
            if current.scope_id != scope or current.entry_ref not in {
                HANDLE_INPUT,
                PREPARE_DETECTION,
            }:
                # 不属于本空间或非可重试入口。
                raise RequestError(404, "not_found", "找不到这次交流。")
            authorization = await store.authorization(db, current.execution_id)
            if authorization.initiator_ref.id != str(account.account_id):
                # 非发起人无权重试。
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
                # 执行状态不允许重试。
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
                # 目标输入不存在或类型不可停止。
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
            # 原请求未落完成回执，无法定位待停止执行。
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
                # 取消请求首次认领，加锁后取消原执行。
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
                    committed_refs=[stopped.result_ref] if stopped.result_ref else [],  # 已落回执则带回引用
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
                accepted_event = draft(
                    scope,
                    facts.ACCEPTED,
                    identity,
                    facts.InputAccepted(
                        records=[facts.record(facts.INPUT, original.input_id, original)],
                        input_ref=identity,
                        adoption_ref=adoption.adoption_ref,
                    ),
                    command.request_id,
                )
                return await service.save_control_result(
                    db,
                    scope,
                    account.account_id,
                    receipt,
                    original.input_id,
                    command.request_id,
                    outcome,
                    [],
                    [],
                    prior_events=[accepted_event],
                )
        # 取消请求已有回执，按既有结果重放。
        return await service.replay_control(scope, receipt)
