"""活动迁移、系统消息和回执在一个空间短事务内共同提交。"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from deermind.abstractions.command_receipts import CommandReceipt, ReceiptCommands
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    PreparedEvents,
    ProducerAccess,
    Ref,
)
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore, lock_scope_sequence
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.public.authentication import AccountView
from deermind.product.public.courses import AdoptionView
from deermind.spaces.interaction import conversation_facts as facts
from deermind.spaces.interaction import (
    detection_plans,
    help_facts,
    history,
    memory_facts,
    provision_facts,
    round_facts,
    task_facts,
    teaching_opportunities,
)
from deermind.spaces.interaction.conversation_facts import ref as ref
from deermind.spaces.interaction.public import (
    CONTROL_ACTIVITY,
    ActivityCommand,
    ActivityControlReceipt,
    ActivityControlResult,
    ActivityNotice,
    ActivityPage,
    ActivityRef,
    ActivityType,
    ActivityView,
    CurrentView,
    DirectoryView,
    MessagePage,
    PresentationCommand,
    PresentationReceipt,
    ResolvedActivityConfig,
    RunState,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

SCOPE = "learning_space"
type Authorize = Callable[[AsyncConnection, AccountView, UUID, bool], Awaitable[AdoptionView]]


def draft(
    scope: UUID,
    event: str,
    owner: Ref,
    payload: EventPayload,
    request_id: str | None,
    *,
    cause: UUID | None = None,
) -> EventDraft:
    """生成业务事件，正文保存于自身记录。"""
    return EventDraft(
        uuid4(),
        event,
        1,
        SCOPE,
        scope,
        owner,
        payload.model_dump(mode="json"),
        request_id,
        causation_event_id=cause,
    )


def activity_change(
    identity: facts.ActivityFact, position: facts.RevisionFact, request_id: str | None
) -> EventDraft:
    """第一版写入活动身份，后续只追加运行修订。"""
    owner = ref("activity", identity.activity_id)
    records = [
        facts.record(facts.REVISION, f"{position.activity_id}@{position.revision}", position)
    ]
    if position.revision == 1:
        # 首版同时写入活动身份记录。
        records.insert(0, facts.record(facts.ACTIVITY, identity.activity_id, identity))
    change = facts.ActivityChanged(
        records=records,
        activity_ref=owner,
        revision_ref=ref("activity", position.activity_id, position.revision),
        parent_ref=ref("activity", identity.parent_id) if identity.parent_id else None,
        node_id=position.node_id,
        reason=position.reason,
        source_input_ref=ref("input", position.source_input_ref)
        if position.source_input_ref
        else None,
        source_trigger_ref=Ref(owner="product", type="event", id=str(position.source_trigger_ref))
        if position.source_trigger_ref
        else None,
    )
    return draft(
        identity.scope_id,
        facts.CHANGED,
        owner,
        change,
        request_id,
        cause=position.source_trigger_ref,
    )


def notice_events(
    scope: UUID,
    activity: UUID,
    message: UUID,
    sequence: int,
    wording: str,
    now: datetime,
    *,
    input_id: UUID | None = None,
    trigger: UUID | None = None,
    request: str | None = None,
) -> tuple[EventDraft, EventDraft]:
    """把系统提示的正文和归属分别写入事实。"""
    message_row = facts.MessageFact(
        message_id=message,
        scope_id=scope,
        message_seq=sequence,
        role="system",
        parts=[ActivityNotice(type="activity_notice", part_id="notice", text=wording)],
        source_input_ref=input_id,
        source_trigger_ref=trigger,
        committed_at=now,
    )
    return (
        message_event(message_row, activity, request),
        assign_message(message_row, activity, request),
    )


def message_event(
    message: facts.MessageFact, activity: UUID | None, request: str | None
) -> EventDraft:
    """正式消息保存原文，活动归属可在分类后补齐。"""
    owner = ref("message", message.message_id)
    return draft(
        message.scope_id,
        facts.RECORDED,
        owner,
        facts.MessageRecorded(
            records=[facts.record(facts.MESSAGE, message.message_id, message)],
            message_ref=owner,
            activity_ref=ref("activity", activity) if activity else None,
            role=message.role,
            source_input_ref=ref("input", message.source_input_ref)
            if message.source_input_ref
            else None,
            source_trigger_ref=Ref(
                owner="product", type="event", id=str(message.source_trigger_ref)
            )
            if message.source_trigger_ref
            else None,
        ),
        request,
        cause=message.source_trigger_ref,
    )


def assign_message(message: facts.MessageFact, activity: UUID, request: str | None) -> EventDraft:
    """将已记录的消息归入活动。"""
    owner = ref("message", message.message_id)
    assignment = facts.AssignmentFact(
        message_id=message.message_id,
        activity_id=activity,
        assigned_by_input_ref=message.source_input_ref,
        source_trigger_ref=message.source_trigger_ref,
        created_at=message.committed_at,
    )
    return draft(
        message.scope_id,
        facts.ASSIGNED,
        owner,
        facts.MessageAssigned(
            records=[facts.record(facts.ASSIGNMENT, message.message_id, assignment)],
            message_ref=owner,
            activity_ref=ref("activity", activity),
        ),
        request,
        cause=message.source_trigger_ref,
    )


def event_access(
    scope: UUID, principal: UUID, source_events: frozenset[UUID] = frozenset()
) -> ProducerAccess:
    return ProducerAccess(
        "interaction",
        Ref(owner="product", type="account", id=str(principal)),
        frozenset({(SCOPE, scope)}),
        source_events,
    )


class Conversation:
    """活动森林的查询和短控制命令。"""

    def __init__(
        self,
        engine: AsyncEngine,
        events: EventStore,
        reader: EventReader,
        receipts: ReceiptCommands[AsyncConnection],
        authorize: Authorize,
    ) -> None:
        self.engine = engine
        self.events = events
        self.reader = reader
        self.receipts = receipts
        self.authorize = authorize

    async def append(
        self,
        db: AsyncConnection,
        scope: UUID,
        principal: UUID,
        request: UUID,
        drafts: Sequence[EventDraft] | PreparedEvents,
        *,
        source_events: frozenset[UUID] = frozenset(),
    ) -> None:
        """在业务锁内分配事件顺序并同步投影。"""
        key = (SCOPE, scope)
        sequence = await lock_scope_sequence(db, *key)
        access = event_access(scope, principal, source_events)
        for item in await self.events.append(
            db,
            access,
            drafts,
            expected_seq={key: sequence},
            commit_id=uuid4(),
            correlation_id=request,
        ):
            # 按事件类型路由到对应事实投影，通用记录走 conversation 投影。
            if item.draft.event_type == detection_plans.PREPARED:
                await detection_plans.project(db, item)
            elif item.draft.event_type in {round_facts.STARTED, round_facts.CLOSED}:
                await round_facts.project(db, item)
            elif item.draft.event_type == help_facts.HANDLED:
                await help_facts.project(db, item)
            elif item.draft.event_type in provision_facts.EVENTS:
                await provision_facts.project(db, item)
            elif item.draft.event_type == memory_facts.SAVED:
                await memory_facts.project(db, item)
            elif item.draft.event_type in {
                task_facts.PRESENTED,
                task_facts.SUBMITTED,
                task_facts.FEEDBACK,
            }:
                await task_facts.project(db, item)
            else:
                await facts.project(db, item)

    async def read(
        self,
        account: AccountView,
        scope: UUID,
        view: DirectoryView,
        *,
        activity: UUID | None,
        anchor: UUID | None,
        after: int,
        cursor: str | None,
        limit: int,
    ) -> CurrentView | ActivityPage | MessagePage:
        """查询位置和历史，读取不占输入入口。"""
        async with self.engine.connect() as db:
            await self.authorize(db, account, scope, False)
            if view == "current":
                # 当前会话视图：叶活动、路径与活动输入。
                return CurrentView(current=await history.current(db, scope))
            if view == "activity_tree":
                # 目录视图：活动森林分页。
                return await history.directory(
                    db, account.account_id, scope, activity, cursor, limit
                )
            return await history.messages(
                db, account.account_id, scope, activity, anchor, after, cursor, limit
            )

    async def replay_control(self, scope: UUID, saved: CommandReceipt) -> ActivityControlReceipt:
        assert saved.result_ref is not None
        event = UUID(saved.result_ref.id)
        data = await self.reader.read_facts(
            SCOPE,
            scope,
            event,
            expected_event_type=facts.COMPLETED,
            correlation_id=saved.request_ref,
            refs=[EventPartRef(event_id=event, record_id=None, path="/control_result")],
        )
        items = data["items"]
        assert isinstance(items, list) and isinstance(items[0], dict)
        return ActivityControlReceipt(
            request_ref=saved.request_ref,
            result=ActivityControlResult.model_validate_json(canonical_json(items[0]["content"])),
        )

    async def receipt(
        self, principal: UUID, _session: UUID, query: ReceiptQuery
    ) -> ReceiptView[ActivityControlResult]:
        """只能由原发起账号补读已完成的命令。"""
        async with self.engine.connect() as db:
            saved = await self.receipts.find_completed_request(
                db, principal, CONTROL_ACTIVITY, query.resource_id, query.request_id
            )
        if saved is None:
            # 无对应已完成控制命令，收据记未找到。
            return ReceiptView[ActivityControlResult](receipt_state="not_found")
        replay = await self.replay_control(query.resource_id, saved)
        return ReceiptView[ActivityControlResult](
            receipt_state="completed",
            receipt_ref=replay.request_ref,
            result=replay.result,
        )

    async def record_presentation(
        self, account: AccountView, scope: UUID, command: PresentationCommand
    ) -> PresentationReceipt:
        """呈现报告只引用本人空间里已经提供的消息片段。"""
        async with self.engine.begin() as db:
            await self.authorize(db, account, scope, False)
            await lock_position(db, scope)
            resource = command.resource_ref
            try:
                message_id = UUID(resource.id)
            except ValueError as exc:
                # 编号非合法 UUID，按找不到显示内容处理。
                raise RequestError(404, "not_found", "找不到显示内容。") from exc
            if command.surface == "textbook" or resource != ref("message", message_id):
                # 教材面不登记呈现；引用也必须指向本空间消息。
                raise RequestError(404, "not_found", "找不到显示内容。")
            count = await db.scalar(
                text(
                    "SELECT jsonb_array_length(parts) FROM interaction.messages "
                    "WHERE scope_id=:scope AND message_id=:id AND role IN ('assistant','system')"
                ),
                {"scope": scope, "id": message_id},
            )
            if count is None:
                # 消息不存在或角色不可呈现，按找不到处理。
                raise RequestError(404, "not_found", "找不到显示内容。")
            allowed = [
                resource.model_copy(update={"path": f"/parts/{index}"}) for index in range(count)
            ]
            reported = command.content_part_refs
            if (
                not reported
                or len(reported) != len({item.path for item in reported})
                or any(item not in allowed for item in reported)
            ):
                # 片段不能为空、路径不得重复，且必须落在该消息允许范围内。
                raise RequestError(400, "invalid_reference", "显示片段不属于该消息。")
            owner = ref("presentation", command.presentation_id)
            previous = await db.scalar(
                text(
                    "SELECT to_jsonb(p)-'source_event_id' FROM interaction.presentations p "
                    "WHERE presentation_id=:id"
                ),
                {"id": command.presentation_id},
            )
            saved = provision_facts.Presentation(
                presentation_id=command.presentation_id,
                scope_id=scope,
                surface=command.surface,
                resource_ref=resource,
                part_refs=reported,
                received_at=datetime.now(UTC),
                client_reported_at=command.client_reported_at,
            )
            if previous:
                # 同一呈现编号已有记录，核对内容是否一致（幂等重放）。
                original = provision_facts.Presentation.model_validate_json(
                    canonical_json(previous)
                )
                if saved.model_copy(update={"received_at": original.received_at}) != original:
                    raise RequestError(409, "identity_conflict", "该回执编号已用于其他内容。")
                return PresentationReceipt(presentation_ref=owner, received_at=original.received_at)
            event = provision_facts.PresentationRecorded(
                presentation_ref=owner,
                surface=saved.surface,
                resource_ref=resource,
                part_refs=saved.part_refs,
                records=[
                    facts.record(provision_facts.PRESENTATION, command.presentation_id, saved)
                ],
            )
            published = draft(
                scope, provision_facts.PRESENTED, owner, event, str(command.presentation_id)
            )
            await self.append(
                db,
                scope,
                account.account_id,
                command.presentation_id,
                [published],
            )
            return PresentationReceipt(presentation_ref=owner, received_at=saved.received_at)

    async def control(
        self, account: AccountView, scope: UUID, command: ActivityCommand
    ) -> ActivityControlReceipt:
        """暂停、恢复和结束都以精确修订及当前路径为依据。"""
        async with self.engine.begin() as db:
            await self.authorize(db, account, scope, False)
            saved = await self.receipts.claim_request(
                db,
                principal_id=str(account.account_id),
                action=CONTROL_ACTIVITY,
                scope_id=str(scope),
                request_id=command.request_id,
                normalized_input=command.model_dump(mode="json", exclude={"request_id"}),
            )
            if saved.result_ref is not None:
                # 命令已完成，按回执重放既有结果。
                return await self.replay_control(scope, saved)
            adoption = await self.authorize(db, account, scope, True)
            await lock_position(db, scope)
            before = await history.current(db, scope)
            if before.active_input_id is not None:
                # 空间尚有进行中输入，拒绝并发控制。
                raise RequestError(409, "interaction_busy", "正在处理上一条，请稍候。")
            if before.current_round and before.current_round.state == "open":
                # 进行中的检测轮须先闭环，再做活动控制。
                raise RequestError(409, "blocked", "请先完成或结束当前检测轮。")
            path = await history.lineage(db, scope, command.activity_ref.activity_id)
            if not path:
                # 沿引用找不到活动路径。
                raise RequestError(404, "not_found", "找不到这个活动。")
            leaf = path[-1]
            if leaf.position.revision != command.expected_activity_revision or (
                leaf.position.revision != command.activity_ref.revision
            ):
                # 实际修订与命令携带的预期/引用修订不符，乐观锁冲突。
                raise RequestError(409, "revision_conflict", "活动已变化，请刷新后再试。")
            before_id = (
                before.current_activity.activity_ref.activity_id
                if before.current_activity
                else None
            )
            changes, current_leaf, wording = await _control_changes(db, command, path, before_id)
            return await self._save_control(
                db, account, scope, adoption, command, saved, changes, current_leaf, leaf, wording
            )

    async def _save_control(
        self,
        db: AsyncConnection,
        account: AccountView,
        scope: UUID,
        adoption: AdoptionView,
        command: ActivityCommand,
        saved: CommandReceipt,
        changes: list[tuple[history.ActivityState, RunState, str]],
        leaf: UUID | None,
        subject: history.ActivityState,
        wording: str,
    ) -> ActivityControlReceipt:
        now = datetime.now(UTC)
        seq, epoch = await next_position(db, scope)
        epoch += 1
        input_id, message = uuid4(), uuid4()
        input_ref = ref("input", input_id)
        input_row = facts.InputFact(
            input_id=input_id,
            scope_id=scope,
            request_id=command.request_id,
            kind="activity_control",
            input=command.model_dump(mode="json"),
            turn_epoch=epoch,
            accepted_at=now,
        )
        accepted = draft(
            scope,
            facts.ACCEPTED,
            input_ref,
            facts.InputAccepted(
                records=[facts.record(facts.INPUT, input_id, input_row)],
                input_ref=input_ref,
                adoption_ref=adoption.adoption_ref,
            ),
            command.request_id,
        )
        history_events: list[EventDraft] = [accepted]
        revision_refs: list[Ref] = []
        for state, run_state, node in changes:
            if run_state == "completed":
                # 活动完成时尝试闭环对应教学机会。
                closure = await teaching_opportunities.closed(
                    db, scope, state, input_id, accepted, "completed"
                )
                if closure:
                    history_events.append(closure)
            revised = revise(
                state.position, run_state, node, command.action, now, input_id=input_id
            )
            revision_refs.append(ref("activity", revised.activity_id, revised.revision))
            history_events.append(activity_change(state.identity, revised, command.request_id))
        history_events.extend(
            notice_events(
                scope,
                subject.identity.activity_id,
                message,
                seq,
                wording,
                now,
                input_id=input_id,
                request=command.request_id,
            )
        )
        await self.append(db, scope, account.account_id, saved.request_ref, history_events)
        await store_position(db, scope, leaf, seq, epoch)
        result = ActivityControlResult(
            current=await history.current(db, scope),
            outcome="changed",
            committed_refs=[*revision_refs, ref("message", message)],
        )
        return await self.save_control_result(
            db,
            scope,
            account.account_id,
            saved,
            input_id,
            command.request_id,
            result,
            [ref("message", message)],
            revision_refs,
        )

    async def save_control_result(
        self,
        db: AsyncConnection,
        scope: UUID,
        principal: UUID,
        saved: CommandReceipt,
        input_id: UUID,
        request_id: str,
        result: ActivityControlResult,
        messages: list[Ref],
        revisions: list[Ref],
        *,
        prior_events: Sequence[EventDraft] = (),
    ) -> ActivityControlReceipt:
        result_id = uuid4()
        result_ref = ref("input_result", result_id)
        record = facts.InputResultFact(
            result_id=result_id,
            input_id=input_id,
            step_key="control",
            outcome="completed",
            message_refs=messages,
            activity_revision_refs=revisions,
            error_ref=None,
            created_at=datetime.now(UTC),
        )
        completed = draft(
            scope,
            facts.COMPLETED,
            result_ref,
            facts.InputCompleted(
                records=[facts.record(facts.RESULT, result_id, record)],
                input_ref=ref("input", input_id),
                result_ref=result_ref,
                control_result=result,
            ),
            request_id,
        )
        await self.append(db, scope, principal, saved.request_ref, [*prior_events, completed])
        await self.receipts.complete_request(db, saved, ref("event", completed.event_id))
        return ActivityControlReceipt(request_ref=saved.request_ref, result=result)

    async def begin(
        self,
        db: AsyncConnection,
        scope: UUID,
        principal: UUID,
        adoption: Ref,
        config: Ref,
        definition: ResolvedActivityConfig,
        activity_type: ActivityType,
        name: str,
        trigger_event_id: UUID,
        *,
        parent_id: UUID | None,
        input_id: UUID | None = None,
        initial_node: str = "start",
        request_ref: UUID | None = None,
    ) -> ActivityRef:
        """建立一个根或直接子活动。调用方先核对固定采用和启动资格。"""
        await lock_position(db, scope)
        before = await history.current(db, scope)
        leaf = before.current_activity
        if parent_id != (leaf.activity_ref.activity_id if leaf else None):
            # 父活动须与当前叶活动一致，否则视为已变更。
            raise RequestError(409, "revision_conflict", "当前活动已变化。")
        if activity_type != definition.blueprint.activity_type:
            raise ValueError("Activity type and fixed blueprint differ")
        if not any(node.node_id == initial_node for node in definition.blueprint.nodes):
            raise ValueError("Unknown initial node")
        now = datetime.now(UTC)
        seq, epoch = await next_position(db, scope)
        new_activity, message = uuid4(), uuid4()
        owner = facts.ActivityFact(
            activity_id=new_activity,
            scope_id=scope,
            root_id=leaf.root_id if leaf else new_activity,
            parent_id=parent_id,
            type=activity_type,
            name=name,
            config_ref=UUID(config.id),
            adoption_ref=UUID(adoption.id),
            started_at=now,
            first_message_ref=message,
        )
        initial = facts.RevisionFact(
            activity_id=new_activity,
            revision=1,
            node_id=initial_node,
            run_state="active",
            return_point=facts.ReturnPoint(parent=leaf.activity_ref, node_id=leaf.node_id)
            if leaf
            else None,
            related_round_ref=None,
            reason="started",
            source_input_ref=input_id,
            source_trigger_ref=trigger_event_id if input_id is None else None,
            created_at=now,
        )
        recorded, assigned = notice_events(
            scope,
            new_activity,
            message,
            seq,
            "开始「" + name + "」。",
            now,
            input_id=input_id,
            trigger=trigger_event_id if input_id is None else None,
        )
        pending = [recorded]
        if parent_id:
            # 子活动：先核对父活动采用依据，再挂起到等待子活动状态。
            parent = await history.activity_at(db, scope, parent_id)
            if parent.identity.adoption_ref != owner.adoption_ref:
                raise RequestError(409, "revision_conflict", "子活动采用依据已变化。")
            if activity_type == "detection" and input_id:
                # 父活动检测机会在子活动开启时闭环。
                closure = await teaching_opportunities.closed(
                    db, scope, parent, input_id, recorded, "completed"
                )
                if closure:
                    pending.append(closure)
            pending.append(
                activity_change(
                    parent.identity,
                    revise(
                        parent.position,
                        "waiting_child",
                        parent.position.node_id,
                        "enter_child",
                        now,
                        input_id=input_id,
                        trigger=trigger_event_id if input_id is None else None,
                    ),
                    None,
                )
            )
        pending.extend((activity_change(owner, initial, None), assigned))
        await self.append(
            db,
            scope,
            principal,
            request_ref or uuid4(),
            [replace(item, causation_event_id=trigger_event_id) for item in pending],
            source_events=frozenset({trigger_event_id}),
        )
        await store_position(db, scope, new_activity, seq, epoch)
        return ActivityRef(activity_id=new_activity, revision=1)


async def lock_position(db: AsyncConnection, scope: UUID) -> None:
    """为空空间建立指针，之后只锁这一个空间。"""
    await db.execute(
        text(
            "INSERT INTO interaction.space_runtime(scope_id) VALUES (:scope) ON CONFLICT DO NOTHING"
        ),
        {"scope": scope},
    )
    await db.execute(
        text("SELECT scope_id FROM interaction.space_runtime WHERE scope_id=:scope FOR UPDATE"),
        {"scope": scope},
    )


async def next_position(db: AsyncConnection, scope: UUID) -> tuple[int, int]:
    """在空间锁内返回下一消息序号和当前受理代次。"""
    row = (
        await db.execute(
            text(
                "SELECT last_message_seq,turn_epoch FROM interaction.space_runtime "
                "WHERE scope_id=:scope"
            ),
            {"scope": scope},
        )
    ).one()
    return int(row.last_message_seq) + 1, int(row.turn_epoch)


async def store_position(
    db: AsyncConnection,
    scope: UUID,
    leaf: UUID | None,
    sequence: int,
    epoch: int,
) -> None:
    """更新正式事实对应的当前指针。"""
    await db.execute(
        text(
            "UPDATE interaction.space_runtime SET current_leaf_ref=:leaf,"
            "last_message_seq=:seq,turn_epoch=:epoch WHERE scope_id=:scope"
        ),
        {"scope": scope, "leaf": leaf, "seq": sequence, "epoch": epoch},
    )


def revise(
    position: facts.RevisionFact,
    state: RunState,
    node: str,
    reason: str,
    now: datetime,
    *,
    input_id: UUID | None = None,
    trigger: UUID | None = None,
) -> facts.RevisionFact:
    """保留返回位置，生成新的活动修订。"""
    return position.model_copy(
        update={
            "revision": position.revision + 1,
            "run_state": state,
            "node_id": node,
            "reason": reason,
            "source_input_ref": input_id,
            "source_trigger_ref": trigger,
            "created_at": now,
        }
    )


async def _control_changes(
    db: AsyncConnection,
    command: ActivityCommand,
    path: list[history.ActivityState],
    current: UUID | None,
) -> tuple[list[tuple[history.ActivityState, RunState, str]], UUID | None, str]:
    leaf = path[-1]
    identity = leaf.identity
    if command.action == "resume":
        # 恢复：查是否存在暂停子活动。
        child = await db.scalar(
            text(
                "SELECT a.activity_id FROM interaction.activities a "
                "JOIN interaction.activity_heads h USING(activity_id) "
                "JOIN interaction.activity_revisions r USING(activity_id,revision) "
                "WHERE a.parent_id=:id AND r.run_state='paused' LIMIT 1"
            ),
            {"id": identity.activity_id},
        )
        if (
            current is not None
            or child
            or any(item.position.run_state != "paused" for item in path)
        ):
            # 已有进行活动、存在子活动，或路径上有非暂停活动，均不可恢复。
            raise RequestError(409, "revision_conflict", "只能恢复已暂停的叶活动。")
        restored: list[tuple[history.ActivityState, RunState, str]] = [
            (item, "waiting_child", item.position.node_id) for item in path[:-1]
        ]
        restored.append((leaf, "active", leaf.position.node_id))
        return restored, identity.activity_id, "继续「" + identity.name + "」。"
    if current != identity.activity_id or leaf.position.run_state != "active":
        # 暂停/结束只能作用于当前活跃叶活动。
        raise RequestError(409, "revision_conflict", "请选择当前进行中的活动。")
    if command.action == "pause":
        # 暂停：路径上全部活动置为 paused，不切叶。
        return (
            [(item, "paused", item.position.node_id) for item in path],
            None,
            "已暂停「" + identity.name + "」。",
        )
    changed: list[tuple[history.ActivityState, RunState, str]] = [(leaf, "completed", "end")]
    returning = return_point(path)
    if returning is None:
        # 根活动结束，无父活动可回退。
        return changed, None, "已结束「" + identity.name + "」。"
    parent, node = returning
    changed.append((parent, "active", node))
    return changed, parent.identity.activity_id, "回到「" + parent.identity.name + "」。"


def return_point(
    path: list[history.ActivityState],
) -> tuple[history.ActivityState, str] | None:
    """结束子活动时验证并返回当初保存的父节点。"""
    if len(path) < 2:
        # 路径不足两层，无子活动返回点。
        return None
    leaf = path[-1]
    parent = path[-2]
    point = leaf.position.return_point
    if (
        point is None
        or point.parent.activity_id != parent.identity.activity_id
        or (parent.position.run_state != "waiting_child")
    ):
        # 返回点缺失、父引用不符或父活动非等待子活动状态，均视为无效。
        raise RuntimeError("Active child has no valid return point")
    return parent, point.node_id


async def return_after_reply(
    db: AsyncConnection,
    scope: UUID,
    leaf: ActivityView,
    sequence: int,
    input_id: UUID,
    request_id: str,
) -> tuple[UUID | None, int, UUID, list[EventDraft]]:
    commands_to_save: list[EventDraft] = []
    sequence += 1
    notice_id = uuid4()
    path = await history.lineage(db, scope, leaf.activity_ref.activity_id)
    returning = return_point(path)
    ending = "已结束「" + leaf.name + "」。"
    next_leaf = None
    if returning is not None:
        # 有返回点：父活动恢复到保存节点，叶切回父活动。
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
    return next_leaf, sequence, notice_id, commands_to_save
