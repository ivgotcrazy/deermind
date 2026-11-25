"""受理教材助手、固定原件依据，并查询已保存的对话和候选。"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4, uuid5

from deermind.abstractions.ai.contracts import ExecutionConfig
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventFilter, EventPartRef
from deermind.abstractions.events import EventDraft, EventPayload, FactRecord, ProducerAccess, Ref
from deermind.abstractions.executions import Authorization, Execution, RunInput, State
from deermind.abstractions.hashing import digest
from deermind.foundation.ai import store as ai_store
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore, lock_scope_sequence
from deermind.foundation.system.executions import commands, store
from deermind.foundation.system.executions.contracts import Caller, Entry, Registry
from deermind.foundation.system.public.errors import Issue, RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.materials import assistant_facts as facts
from deermind.product.materials.facts import IMPORT, MaterialImportFact, record
from deermind.product.materials.proposals import MaterialProposal
from deermind.product.materials.receiving import MaterialReceiving, import_ref
from deermind.product.public.authentication import SessionView
from deermind.product.public.material_assistant import (
    CONVERSE,
    MaterialBatchView,
    MaterialHistory,
    MaterialMessageInput,
    MaterialMessagePart,
    MaterialMessageView,
    MaterialTurnAcceptance,
    MaterialTurnResult,
    PreviousMaterialBatch,
    TurnOutcome,
)
from deermind.spaces.domain.public import SourceRef
from pydantic import JsonValue, TypeAdapter
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

SCOPE = "material_import"
WHOLE_BOOK = ("整本", "全册", "全部", "全书")
WORKFLOW = "product.material_assistant"
_LIST_OF_OBJECTS = TypeAdapter(list[dict[str, JsonValue]])


def turn_ref(identity: UUID) -> Ref:
    return Ref(owner="product", type="material_turn", id=str(identity))


def _turn_identity(principal: UUID, identity: UUID, request_id: str) -> UUID:
    return uuid5(identity, f"{CONVERSE}:{principal}:{request_id}")


def _turn_from_row(row: RowMapping) -> facts.TurnFact:
    return facts.TurnFact.model_validate_json(
        canonical_json(
            {
                key: str(value) if isinstance(value, (UUID, datetime)) else value
                for key, value in row.items()
                if key != "source_event_id"
            }
        )
    )


class MaterialAssistant:
    def __init__(
        self,
        engine: AsyncEngine,
        materials: MaterialReceiving,
        events: EventStore,
        reader: EventReader,
        attachments: FactAttachments,
        config: ExecutionConfig | None,
        queue: str,
    ) -> None:
        self.engine = engine
        self.materials = materials
        self.events = events
        self.reader = reader
        self.attachments = attachments
        self.config = config
        self.registry = Registry(
            [
                Entry(
                    "product",
                    CONVERSE,
                    "ai_operation",
                    Ref(owner="product", type="operation", id=CONVERSE, version=1),
                    WORKFLOW,
                    queue,
                    self._lock,
                    self._check,
                    self._finalize,
                )
            ]
        )

    async def _lock(self, connection: AsyncConnection, kind: str, identity: UUID) -> None:
        if kind != SCOPE:
            # 助手执行只允许绑定教材导入作用域。
            raise PermissionError("Wrong material import scope")
        # 失败收尾需要锁住已软删除的导入，业务校验另查其 active 状态。
        value = await connection.scalar(
            text("SELECT import_id FROM product.material_import WHERE import_id=:id FOR UPDATE"),
            {"id": identity},
        )
        if value is None:
            raise PermissionError("Material import does not exist")

    async def _check(
        self, connection: AsyncConnection, work: Execution, _granted: Authorization, action: str
    ) -> None:
        if action in {"read", "cancel"}:
            # 只读与取消不占用导入写归属，直接放行。
            return
        value = (
            await connection.execute(
                text(
                    "SELECT status,active_request_ref FROM product.material_import "
                    "WHERE import_id=:id"
                ),
                {"id": work.scope_id},
            )
        ).one()
        if value != ("active", UUID(work.input_ref.id)):
            # 导入已停用，或占用请求已被其他轮次接管。
            raise PermissionError("Material turn no longer owns the import")

    async def _turn(
        self, connection: AsyncConnection, identity: UUID, scope: UUID
    ) -> facts.TurnFact:
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT * FROM product.material_turn "
                        "WHERE request_ref=:id AND import_id=:scope"
                    ),
                    {"id": identity, "scope": scope},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LookupError("Material turn does not exist")
        # 命中轮次记录后转为事实模型。
        return _turn_from_row(row)

    async def _manifest(
        self,
        connection: AsyncConnection,
        import_id: UUID,
        command: MaterialMessageInput,
        earlier_pages: set[str] | None,
    ) -> tuple[list[dict[str, JsonValue]], list[str]]:
        rows = (
            (
                await connection.execute(
                    text(
                        "SELECT source_id,file_id,original_name,sha256,pages "
                        "FROM product.material_source WHERE import_id=:id ORDER BY source_order"
                    ),
                    {"id": import_id},
                )
            )
            .mappings()
            .all()
        )
        selection = command.selection
        if (
            selection is None
            and earlier_pages is None
            and not any(term in command.message for term in WHOLE_BOOK)
        ):
            # 既未选原件、又未指整本，消息也未暗示全册，缺少取材范围。
            return [], ["请明确要解析整本教材，或选择需要核对的原件及页码。"]
        selected = {item.source_id: item for item in selection.source_refs} if selection else {}
        if selection and (
            selection.import_id != import_id or len(selected) != len(selection.source_refs)
        ):
            raise RequestError(400, "invalid_reference", "原件范围与当前教材不符。")
        if selected and not selected.keys() <= {row["source_id"] for row in rows}:
            raise RequestError(400, "invalid_reference", "原件范围包含其他教材或不存在的文件。")
        pages: list[dict[str, JsonValue]] = []
        missing: list[str] = []
        for row in rows:
            if selected and row["source_id"] not in selected:
                # 未被选中的原件跳过。
                continue
            items = row["pages"]
            supplied = selected.get(row["source_id"])
            first = supplied.first_page if supplied else 1
            last = supplied.last_page if supplied else len(items)
            if first > last or last > len(items):
                # 页码区间越界或起止颠倒，记缺口并跳过该原件。
                missing.append(f"{row['original_name']} 缺少文件内第 {first}–{last} 页。")
                continue
            for item in items[first - 1 : last]:
                if (
                    selection is None
                    and earlier_pages is not None
                    and item["page_id"] not in earlier_pages
                ):
                    # 沿用上一轮已读页集合，跳过本次未在其中的页。
                    continue
                pages.append(
                    {
                        "page_id": str(item["page_id"]),
                        "file_page": item["file_page_index"],
                        "file_id": str(row["file_id"]),
                        "source_id": str(row["source_id"]),
                        "sha256": row["sha256"],
                        "original_name": row["original_name"],
                    }
                )
        # 有缺口报缺口；无缺口但一页未取到时提示空范围。
        return pages, missing or ([] if pages else ["此范围没有可供核对的原件。"])

    async def _previous_batch(
        self,
        connection: AsyncConnection,
        identity: UUID,
        reference: PreviousMaterialBatch,
    ) -> RowMapping:
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT b.* FROM product.material_candidate_batch b "
                        "JOIN product.material_turn t ON b.turn_ref=t.request_ref "
                        "WHERE b.batch_id=:batch AND b.batch_revision=:revision "
                        "AND t.import_id=:import"
                    ),
                    {
                        "batch": reference.batch_id,
                        "revision": reference.batch_revision,
                        "import": identity,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise RequestError(404, "not_found", "找不到这份候选的固定版本。")
        if row["decision_state"] not in {"pending", "adopted"}:
            # 已拒绝或已被取代的批次不能作为前序依据。
            raise RequestError(409, "revision_conflict", "这份候选已失效，请引用当前候选。")
        return row

    async def accept(
        self, session: SessionView, identity: UUID, command: MaterialMessageInput
    ) -> MaterialTurnAcceptance:
        principal = self.materials.administrator(session)
        actor = Ref(owner="product", type="account", id=str(principal))
        action_id = _turn_identity(principal, identity, command.request_id)
        signature = digest(command.model_dump(mode="json"))
        config = self.config
        if config is None:
            # 模型执行配置缺失，无法发起助手轮次。
            raise RequestError(503, "configuration_unavailable", "教材助手的模型服务尚未配置。")
        async with self.engine.begin() as connection:
            imported = await self.materials.read_import(connection, identity, lock=True)
            try:
                previous = await self._turn(connection, action_id, identity)
            except LookupError:
                # 同一请求键无历史轮次，视为首次提交。
                previous = None
            if previous is not None:
                if previous.input_digest != signature:
                    # 幂等键被不同输入复用，属冲突。
                    raise RequestError(409, "request_conflict", "此请求编号已用于另一条消息。")
                return MaterialTurnAcceptance(
                    request_ref=action_id, execution_ref=previous.runtime_ref
                )
            if imported["active_request_ref"] is not None:
                # 导入正被另一轮次占用，避免并发并发处理。
                raise RequestError(409, "assistant_busy", "正在处理上一条消息，请稍后再发送。")
            if (
                command.selection is not None
                and command.selection.basis_revision != imported["content_revision"]
            ):
                raise RequestError(409, "revision_conflict", "教材内容已更新，请重新选择引用。")
            prior_batch = command.previous_batch_ref
            earlier_pages = None
            if prior_batch is not None:
                # 引用前序批次时，取出其已读页集合作为上下文范围。
                earlier = await self._previous_batch(connection, identity, prior_batch)
                earlier_pages = {str(ref["source_id"]) for ref in earlier["read_set"]}
            pages, gaps = await self._manifest(connection, identity, command, earlier_pages)
            timestamp = datetime.now(UTC)
            message_id = uuid4()
            work_id = uuid4()
            sources = [
                Ref(owner="product", type="material_page", id=str(page["page_id"]))
                for page in pages
            ]
            turn = facts.TurnFact(
                request_ref=action_id,
                import_id=identity,
                input_digest=signature,
                input={
                    "message": command.message,
                    "message_ref": str(message_id),
                    "pages": [page for page in pages],
                    "gaps": [message for message in gaps],
                    "source_revision": imported["source_revision"],
                    "basis_revision": imported["content_revision"],
                    "request_id": command.request_id,
                    "previous_batch": prior_batch.model_dump(mode="json") if prior_batch else None,
                },
                state="accepted",
                runtime_ref=work_id,
                work_state_ref=None,
                result_ref=None,
                error=None,
                created_at=timestamp,
                updated_at=timestamp,
            )
            user = self._message(
                turn, message_id, imported["next_message_seq"], "user", command.message, sources
            )
            await self._publish(
                connection,
                actor,
                turn,
                facts.RECEIVED,
                facts.AssistantMessageReceived(
                    records=[
                        record(facts.TURN, action_id, turn),
                        record(facts.MESSAGE, message_id, user),
                        record(IMPORT, identity, self._advance(imported, timestamp)),
                    ],
                    import_id=identity,
                    request_ref=action_id,
                    message_ref=message_id,
                ),
            )
            await self._occupation(
                connection, identity, action_id, imported["next_message_seq"] + 1
            )
            accepted = await store.accept(
                connection,
                self.registry,
                Caller(actor, "product", frozenset({(SCOPE, identity)}), frozenset({"accept"})),
                entry_name=CONVERSE,
                scope_kind=SCOPE,
                scope_id=identity,
                acceptance_key=str(action_id),
                input_ref=turn_ref(action_id),
                seconds=1200,
                basis_refs=sources,
                ai_config_ref=work_id,
            )
            await ai_store.pin(connection, accepted, config)
        return MaterialTurnAcceptance(request_ref=action_id, execution_ref=work_id)

    @staticmethod
    def _advance(row: RowMapping, time: datetime) -> MaterialImportFact:
        return MaterialImportFact(
            import_id=row["import_id"],
            textbook_id=row["textbook_id"],
            status=row["status"],
            revision=row["revision"] + 1,
            source_revision=row["source_revision"],
            content_revision=row["content_revision"],
            created_at=row["created_at"],
            updated_at=time,
        )

    @staticmethod
    def _message(
        turn: facts.TurnFact,
        identity: UUID,
        seq: int,
        role: Literal["user", "assistant"],
        value: str,
        refs: list[Ref],
    ) -> MaterialMessageView:
        return MaterialMessageView(
            message_id=identity,
            import_id=turn.import_id,
            seq=seq,
            role=role,
            body=[MaterialMessagePart(part_id="text", type="text", text=value)],
            explicit_refs=refs,
            turn_ref=turn.request_ref,
            created_at=datetime.now(UTC),
        )

    async def _occupation(
        self, connection: AsyncConnection, import_id: UUID, active: UUID | None, next_seq: int
    ) -> None:
        await connection.execute(
            text(
                "UPDATE product.material_import SET "
                "active_request_ref=:active,next_message_seq=:seq "
                "WHERE import_id=:id"
            ),
            {"id": import_id, "active": active, "seq": next_seq},
        )

    async def _publish(
        self,
        connection: AsyncConnection,
        actor: Ref,
        turn: facts.TurnFact,
        kind: str,
        payload: EventPayload,
    ) -> None:
        scope = (SCOPE, turn.import_id)
        sequence = await lock_scope_sequence(connection, *scope)
        (event,) = await self.events.append(
            connection,
            ProducerAccess("product", actor, frozenset({scope})),
            [
                EventDraft(
                    uuid4(),
                    kind,
                    1,
                    SCOPE,
                    turn.import_id,
                    import_ref(turn.import_id),
                    payload.model_dump(mode="json"),
                    str(turn.request_ref),
                    source_execution_ref=None if kind == facts.RECEIVED else turn.runtime_ref,
                )
            ],
            commit_id=uuid4(),
            correlation_id=turn.request_ref,
            expected_seq={scope: sequence},
        )
        await facts.project(connection, event)

    async def current_input(self, run: RunInput) -> tuple[Execution, facts.TurnFact]:
        async with self.engine.begin() as connection:
            work = await store.active(connection, self.registry, run, "step")
            return work, await self._turn(connection, UUID(work.input_ref.id), work.scope_id)

    async def previous_context(self, turn: facts.TurnFact) -> str:
        reference = turn.input.get("previous_batch")
        if reference is None:
            # 无前序批次则不带历史上下文。
            return ""
        fixed = PreviousMaterialBatch.model_validate(reference)
        async with self.engine.connect() as connection:
            previous = await self._previous_batch(connection, turn.import_id, fixed)
            rows = (
                await connection.scalars(
                    text(
                        "SELECT to_jsonb(c)-'source_event_id' FROM product.material_candidate c "
                        "WHERE c.batch_id=:id AND c.import_id=:import ORDER BY c.local_key"
                    ),
                    {"id": fixed.batch_id, "import": turn.import_id},
                )
            ).all()
        return canonical_json(
            {"chapters": previous["diff_summary"]["chapters"], "items": list(rows)}
        )

    async def finish(
        self,
        run: RunInput,
        proposal: MaterialProposal | None,
        shown: list[SourceRef],
        reply: str,
        outcome: TurnOutcome,
        issues: list[Issue],
    ) -> None:
        async with self.engine.begin() as connection:
            saved = await store.lock_owned(connection, self.registry, run.execution_id)
            if saved.state == "completed":
                # 已完成的执行重复收尾直接返回。
                return
            work = await store.active(connection, self.registry, run, "finish")
            turn = await self._turn(connection, UUID(work.input_ref.id), work.scope_id)
            imported = await self.materials.read_import(connection, work.scope_id, lock=True)
            actor = (await store.authorization(connection, work.execution_id)).initiator_ref
            batches: list[Ref] = []
            if proposal is not None and (
                proposal.changes or proposal.catalog_changes or proposal.retire
            ):
                # 提案含改动、目录调整或退役项，先落候选批次。
                batches.append(
                    await self._publish_candidates(
                        connection, actor, turn, imported, proposal, shown
                    )
                )
            next_seq = await self._save_outcome(
                connection, turn, imported, actor, reply, outcome, issues, batches
            )
            await commands.complete(connection, self.registry, run, turn_ref(turn.request_ref))
            await self._occupation(connection, turn.import_id, None, next_seq)

    async def _publish_candidates(
        self,
        connection: AsyncConnection,
        actor: Ref,
        turn: facts.TurnFact,
        imported: RowMapping,
        proposal: MaterialProposal,
        shown: list[SourceRef],
    ) -> Ref:
        proposal = proposal.bind_sources(shown)
        timestamp = datetime.now(UTC)
        batch_id = uuid4()
        batch_ref = Ref(owner="product", type="candidate_batch", id=str(batch_id), revision=1)
        prior_ref = turn.input.get("previous_batch")
        previous_rows: dict[str, facts.CandidateFact] = {}
        chapter_names: dict[str, UUID] = {}
        if prior_ref is not None:
            # 载入前序批次快照，供修订与退役定位旧候选。
            previous = PreviousMaterialBatch.model_validate(prior_ref)
            snapshot = await self._previous_batch(connection, turn.import_id, previous)
            sources = (
                await connection.scalars(
                    text(
                        "SELECT to_jsonb(c)-'source_event_id' FROM product.material_candidate c "
                        "WHERE c.batch_id=:id AND c.import_id=:scope"
                    ),
                    {"id": previous.batch_id, "scope": turn.import_id},
                )
            ).all()
            for row in sources:
                prior = facts.CandidateFact.model_validate_json(canonical_json(row))
                previous_rows[str(prior.candidate_id)] = prior
            for section in snapshot["diff_summary"]["chapters"]:
                # 记录章节名到前序章节标识的映射，便于目录调整复用。
                chapter_names[section["name"]] = UUID(section["chapter_id"])
        candidates: dict[str, tuple[UUID, int]] = {}
        replaced: set[str] = set()
        for item in proposal.changes:
            if item.replaces is None:
                # 无替换目标：新建候选，版本从 1 起。
                candidates[item.local_key] = (uuid4(), 1)
                continue
            old = previous_rows.get(item.replaces)
            if old is None or old.kind != item.kind or item.replaces in replaced:
                # 修订目标须在前序批次内、类型一致且未被重复替换。
                raise ValueError("Correction target is outside the referenced batch")
            latest = await connection.scalar(
                text(
                    "SELECT max(candidate_revision) FROM product.material_candidate "
                    "WHERE candidate_id=:id"
                ),
                {"id": old.candidate_id},
            )
            candidates[item.local_key] = (old.candidate_id, int(latest) + 1)
            replaced.add(item.replaces)
        chapters = {
            item.local_key: chapter_names.get(item.name) or uuid4()
            for item in proposal.catalog_changes
        }
        reference_map = {
            item.source_id: Ref(owner="product", type="material_page", id=item.source_id)
            for item in shown
        }
        basis = turn.input["basis_revision"]
        assert isinstance(basis, int)
        rows: list[FactRecord] = []
        writes: list[dict[str, JsonValue]] = []
        for target in proposal.retire:
            old = previous_rows.get(target)
            if old is None or target in replaced:
                # 退役目标须在前序批次内，且不能同时又是被替换对象。
                raise ValueError(
                    "Retirement target is outside the referenced batch or also replaced"
                )
            writes.append(
                {
                    "candidate_id": target,
                    "chapter_id": old.chapter_ref.id,
                    "action": "retire",
                    "previous": target,
                    "candidate_revision": old.candidate_revision,
                    "title": old.body["title"],
                }
            )
        # 为每条改动组装候选事实记录与写集条目。
        for entry in proposal.changes:
            identity, revision = candidates[entry.local_key]
            row = facts.CandidateFact(
                candidate_id=identity,
                candidate_revision=revision,
                batch_id=batch_id,
                import_id=turn.import_id,
                local_key=entry.local_key,
                kind=entry.kind,
                chapter_ref=Ref(
                    owner="product",
                    type="material_chapter",
                    id=str(chapters[entry.chapter_key]),
                    revision=1,
                ),
                body={
                    "title": entry.title,
                    "content": entry.content.model_dump(mode="json"),
                    "teaching_aids": [aid.model_dump(mode="json") for aid in entry.teaching_aids],
                },
                parent_ref=Ref(
                    owner="product",
                    type="material_candidate",
                    id=str(candidates[entry.parent_key][0]),
                    revision=candidates[entry.parent_key][1],
                )
                if entry.parent_key
                else None,
                source_refs=[reference_map[ref.source_id] for ref in entry.content.source_refs],
                basis_revision=basis,
                created_at=timestamp,
            )
            rows.append(record(facts.CANDIDATE, identity, row))
            writes.append(
                {
                    "candidate_id": str(identity),
                    "chapter_id": row.chapter_ref.id,
                    "action": "replace" if entry.replaces else "add",
                    "previous": entry.replaces,
                    "candidate_revision": revision,
                    "reason": entry.reason,
                }
            )
        batch = facts.CandidateBatchFact(
            batch_id=batch_id,
            batch_revision=1,
            turn_ref=turn.request_ref,
            scope={"import_id": str(turn.import_id), "basis_revision": basis},
            read_set=[ref.model_dump(mode="json") for ref in shown],
            write_set=writes,
            coverage={
                "pages": [item.model_dump(mode="json") for item in proposal.coverage],
                "issues": [issue for issue in proposal.issues],
                "questions": [question for question in proposal.questions],
                "complete": proposal.outcome == "proposal"
                and all(item.status != "unreadable" for item in proposal.coverage),
            },
            diff_summary={
                "chapters": [
                    {**item.model_dump(mode="json"), "chapter_id": str(chapters[item.local_key])}
                    for item in proposal.catalog_changes
                ],
                "previous_batch": turn.input.get("previous_batch"),
            },
            decision_state="pending",
            decision_revision=1,
            created_at=timestamp,
        )
        previous_records: list[FactRecord] = []
        previous = turn.input.get("previous_batch")
        if previous is not None and batch.coverage["complete"]:
            fixed = PreviousMaterialBatch.model_validate(previous)
            source = await self._previous_batch(connection, turn.import_id, fixed)
            if source["decision_state"] == "pending":
                # 新批次覆盖完整时，把仍在待审的旧批次标记为已被取代。
                body = {
                    key: str(value) if isinstance(value, (UUID, datetime)) else value
                    for key, value in source.items()
                    if key != "source_event_id"
                }
                prior = facts.CandidateBatchFact.model_validate_json(canonical_json(body))
                changed = prior.model_copy(
                    update={
                        "decision_state": "superseded",
                        "decision_revision": prior.decision_revision + 1,
                    }
                )
                previous_records.append(record(facts.BATCH, fixed.batch_id, changed))
        await self._publish(
            connection,
            actor,
            turn,
            facts.PROPOSED,
            facts.CandidatePrepared(
                records=[
                    record(facts.BATCH, batch_id, batch),
                    *previous_records,
                    *rows,
                    record(IMPORT, turn.import_id, self._advance(imported, timestamp)),
                ],
                import_id=turn.import_id,
                request_ref=turn.request_ref,
                batch_ref=batch_ref,
            ),
        )
        return batch_ref

    async def _save_outcome(
        self,
        connection: AsyncConnection,
        turn: facts.TurnFact,
        imported: RowMapping,
        actor: Ref,
        reply: str,
        outcome: TurnOutcome,
        issues: list[Issue],
        batches: list[Ref],
    ) -> int:
        timestamp = datetime.now(UTC)
        reply_id = uuid4()
        seq: int = imported["next_message_seq"]
        completed = turn.model_copy(
            update={
                "state": outcome,
                "result_ref": batches[0] if batches else None,
                "error": {"code": "assistant_failed", "message": reply, "retryable": True}
                if outcome == "failed"
                else None,
                "updated_at": timestamp,
            }
        )
        user_id = UUID(str(turn.input["message_ref"]))
        message = self._message(turn, reply_id, seq, "assistant", reply, batches)
        await self._publish(
            connection,
            actor,
            turn,
            facts.FINISHED,
            facts.TurnFinished(
                records=[
                    record(facts.TURN, turn.request_ref, completed),
                    record(facts.MESSAGE, reply_id, message),
                    record(IMPORT, turn.import_id, self._advance(imported, timestamp)),
                ],
                import_id=turn.import_id,
                request_ref=turn.request_ref,
                message_ref=user_id,
                reply_ref=reply_id,
                outcome=outcome,
                candidate_batch_refs=batches,
                issues=issues,
            ),
        )
        return seq + 1

    async def _finalize(
        self, connection: AsyncConnection, work: Execution, state: State, _result: Ref | None
    ) -> None:
        if state not in {"failed", "cancelled"}:
            # 成功收尾无需补偿处理。
            return
        turn = await self._turn(connection, UUID(work.input_ref.id), work.scope_id)
        if turn.state != "accepted":
            # 轮次已落定过结果，避免重复补偿。
            return
        imported = (
            (
                await connection.execute(
                    text("SELECT * FROM product.material_import WHERE import_id=:id"),
                    {"id": work.scope_id},
                )
            )
            .mappings()
            .one()
        )
        if imported["active_request_ref"] == turn.request_ref:
            # 仅当本次执行仍持有导入占用时才释放占用并落失败/取消结果。
            granted = await store.authorization(connection, work.execution_id)
            next_seq = await self._save_outcome(
                connection,
                turn,
                imported,
                granted.initiator_ref,
                "教材处理已停止。"
                if state == "cancelled"
                else "本次处理未完成，请检查原件或稍后再试。",
                "cancelled" if state == "cancelled" else "failed",
                [],
                [],
            )
            await self._occupation(connection, turn.import_id, None, next_seq)

    async def receipt(
        self, principal: UUID, _session_id: UUID, query: ReceiptQuery
    ) -> ReceiptView[MaterialTurnResult]:
        try:
            async with self.engine.connect() as connection:
                turn = await self._turn(
                    connection,
                    _turn_identity(principal, query.resource_id, query.request_id),
                    query.resource_id,
                )
        except LookupError:
            # 无对应轮次收据，按未找到返回。
            return ReceiptView[MaterialTurnResult](receipt_state="not_found")
        status = "accepted" if turn.state == "accepted" else "completed"
        result = None
        if status == "completed":
            # 已完成轮次回读结束事件事实以组装结果。
            found = await self.reader.query_metadata(
                SCOPE,
                turn.import_id,
                filters=EventFilter(event_types=(facts.FINISHED,), correlation_id=turn.request_ref),
                limit=1,
            )
            metadata = _LIST_OF_OBJECTS.validate_python(found["items"])
            event_id = UUID(str(metadata[0]["event_id"]))
            items = await self.reader.read_facts(
                SCOPE,
                turn.import_id,
                event_id,
                refs=[EventPartRef(event_id=event_id, record_id=None, path="")],
                expected_event_type=facts.FINISHED,
                correlation_id=turn.request_ref,
                schema_version=1,
            )
            view = _LIST_OF_OBJECTS.validate_python(items["items"])[0]["content"]
            result = MaterialTurnResult.model_validate(view, extra="ignore")
        return ReceiptView[MaterialTurnResult](
            receipt_state=status,
            receipt_ref=turn.request_ref,
            result=result,
            execution_ref=turn.runtime_ref,
            business_state=turn.state,
        )

    async def history(
        self, session: SessionView, import_id: UUID, after: int, upper: int | None, limit: int
    ) -> MaterialHistory:
        self.materials.administrator(session)
        async with self.engine.connect() as connection:
            imported = await self.materials.read_import(connection, import_id)
            # 上界取请求上限与当前最后消息序号的较小值。
            horizon = (
                min(upper, imported["next_message_seq"] - 1)
                if upper is not None
                else imported["next_message_seq"] - 1
            )
            rows = (
                await connection.scalars(
                    text(
                        "SELECT to_jsonb(m)-'source_event_id' FROM product.material_message m "
                        "WHERE import_id=:id AND seq>:after AND seq<=:upper "
                        "ORDER BY seq LIMIT :limit"
                    ),
                    {"id": import_id, "after": after, "upper": horizon, "limit": limit + 1},
                )
            ).all()
        messages = [
            MaterialMessageView.model_validate_json(canonical_json(row)) for row in rows[:limit]
        ]
        last = messages[-1].seq if messages else after
        return MaterialHistory(
            items=messages,
            upper_seq=horizon,
            last_seq=last,
            next_cursor=f"{horizon}.{last}" if len(rows) > limit else None,
            active_request_ref=imported["active_request_ref"],
        )

    async def read_batch(
        self, session: SessionView, import_id: UUID, batch_id: UUID
    ) -> MaterialBatchView:
        self.materials.administrator(session)
        async with self.engine.connect() as connection:
            await self.materials.read_import(connection, import_id)
            keys = {"id": batch_id, "import_id": import_id}
            batch = await connection.scalar(
                text(
                    "SELECT to_jsonb(b)-'source_event_id' FROM product.material_candidate_batch b "
                    "JOIN product.material_turn t ON t.request_ref=b.turn_ref "
                    "WHERE b.batch_id=:id AND t.import_id=:import_id"
                ),
                keys,
            )
            if batch is None:
                raise RequestError(404, "not_found", "找不到这批教材候选。")
            # 批次与候选明细一并读出。
            candidates = (
                await connection.scalars(
                    text(
                        "SELECT to_jsonb(c)-'source_event_id' FROM product.material_candidate c "
                        "WHERE c.batch_id=:id AND c.import_id=:import_id ORDER BY c.local_key"
                    ),
                    keys,
                )
            ).all()
        if len(canonical_json([batch, *candidates]).encode()) > 4 * 1024**2:
            # 结果体积超限，提示收窄取材范围。
            raise RequestError(413, "payload_too_large", "候选过多，请按较小的原件范围重新核对。")
        return MaterialBatchView(batch=batch, items=list(candidates))
