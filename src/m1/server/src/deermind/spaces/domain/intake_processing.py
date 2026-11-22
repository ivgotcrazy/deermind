"""管理员确定入库时，把领域版本、待办结果及收据一次提交。"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid5

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from deermind.abstractions.delivery import Acceptance, EventNotice
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import EventDraft, FactRecord, ProducerAccess, Ref
from deermind.abstractions.hashing import digest
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.spaces.domain import facts as definition_facts
from deermind.spaces.domain import instance_facts as facts
from deermind.spaces.domain.analysis import DomainAnalysis
from deermind.spaces.domain.definitions import apply_domain_event
from deermind.spaces.domain.instances import (
    instance_event,
    load_instance,
    require_definition,
    validate_instance,
)
from deermind.spaces.domain.intake import ITEM, IntakeItem
from deermind.spaces.domain.public import (
    PROCESS_INTAKE,
    InstanceView,
    IntakeAction,
    IntakeActionReceipt,
    IntakeActionResult,
    KnowledgeRef,
    ReferenceSolution,
    RichContent,
    SolutionRef,
    TaskDefinition,
    TaskInstance,
    TaskRef,
)


@dataclass(frozen=True)
class Plan:
    result: IntakeActionResult
    drafts: list[EventDraft]
    instance_version: facts.InstanceVersion | None = None


def _record(name: str, identity: str, body: dict[str, object]) -> FactRecord:
    return FactRecord.model_validate(
        {
            "record_id": identity,
            "record_type": name,
            "schema_version": 1,
            "content": {"storage": "inline", "value": body},
        }
    )


class IntakeProcessing:
    def __init__(self, analysis: DomainAnalysis) -> None:
        self.analysis = analysis
        self.intake = analysis.intake
        self.engine = analysis.engine

    async def invalidate_source(
        self,
        connection: AsyncConnection,
        notice: EventNotice,
    ) -> Acceptance:
        selected = {"source": f"{notice.scope_id}:%"}
        domains = (
            await connection.scalars(
                text(
                    "SELECT DISTINCT domain_id FROM domain.intake_item "
                    "WHERE state='pending' AND candidate_key LIKE :source ORDER BY domain_id"
                ),
                selected,
            )
        ).all()
        removed: list[Ref] = []
        for domain_id in domains:
            scope = ("domain", domain_id)
            await self.analysis.lock(connection, *scope)
            rows = (
                await connection.scalars(
                    text(
                        "SELECT to_jsonb(i)-'source_event_id' FROM domain.intake_item i "
                        "WHERE domain_id=:domain AND state='pending' "
                        "AND candidate_key LIKE :source "
                        "ORDER BY item_id"
                    ),
                    {**selected, "domain": domain_id},
                )
            ).all()
            drafts: list[EventDraft] = []
            for row in rows:
                item = IntakeItem.model_validate_json(canonical_json(row))
                item = item.model_copy(update={"revision": item.revision + 1, "state": "removed"})
                reference = item.reference()
                payload = facts.SourceInvalidated(
                    item_ref=reference,
                    import_id=notice.scope_id,
                    trigger_event_id=notice.event_id,
                    records=[_record(ITEM, reference.id, item.model_dump(mode="json"))],
                )
                drafts.append(
                    EventDraft(
                        uuid4(),
                        facts.INVALIDATED,
                        1,
                        *scope,
                        reference,
                        payload.model_dump(mode="json"),
                        None,
                        notice.event_id,
                    )
                )
                removed.append(reference)
            if drafts:
                sequence = await lock_scope_sequence(connection, *scope)
                actor = Ref(owner="domain", type="service", id="material-invalidation")
                events = await self.intake.store.append(
                    connection,
                    ProducerAccess(
                        "domain", actor, frozenset({scope}), frozenset({notice.event_id})
                    ),
                    drafts,
                    commit_id=uuid4(),
                    correlation_id=notice.event_id,
                    expected_seq={scope: sequence},
                )
                for event in events:
                    await facts.project_items(connection, event)
        return Acceptance(
            disposition="accepted" if removed else "ignored",
            arrangement_refs=removed,
        )

    async def _children(self, connection: AsyncConnection, item_id: UUID) -> list[IntakeItem]:
        rows = (
            await connection.scalars(
                text(
                    "SELECT to_jsonb(c)-'source_event_id' FROM domain.intake_item c "
                    "WHERE parent_item_id=:id AND state='pending' ORDER BY item_id"
                ),
                {"id": item_id},
            )
        ).all()
        return [IntakeItem.model_validate_json(canonical_json(row)) for row in rows]

    async def _result(
        self,
        domain: UUID,
        event: UUID,
    ) -> IntakeActionResult:
        raw = await self.intake.reader.read_facts(
            "domain",
            domain,
            event,
            expected_event_type=facts.PROCESSED,
            refs=[EventPartRef(event_id=event, record_id=None, path="/result")],
        )
        parts = raw["items"]
        assert isinstance(parts, list) and isinstance(parts[0], dict)
        return IntakeActionResult.model_validate_json(canonical_json(parts[0]["content"]))

    async def _knowledge(
        self,
        connection: AsyncConnection,
        item: IntakeItem,
        command: IntakeAction,
        actor: Ref,
        request: UUID,
    ) -> tuple[Ref, list[EventDraft]]:
        if item.kind != "kc" or (command.definition is None) == (command.existing_kc_ref is None):
            raise RequestError(400, "invalid_request", "请选择一个已有知识成分或填写新定义。")
        if command.existing_kc_ref is not None:
            ref = command.existing_kc_ref
            await require_definition(connection, item.domain_id, ref)
            return definition_facts.version_ref(ref), []
        assert command.definition is not None
        ref = KnowledgeRef(kind="kc", object_id=uuid5(request, "kc"), version=1)
        reference = definition_facts.version_ref(ref)
        body = definition_facts.DomainVersion(
            object_id=ref.object_id,
            version=1,
            content_schema_version=1,
            content=command.definition,
            is_deleted=False,
            created_at=datetime.now(UTC),
            created_by=actor,
            change_note="采用教材待入库知识",
        )
        payload = definition_facts.DomainSaved(
            object_ref=ref,
            previous_ref=None,
            action="create",
            request_ref=request,
            records=[
                _record(
                    definition_facts.RECORD_TYPE,
                    definition_facts.RECORD_ID,
                    body.model_dump(mode="json"),
                )
            ],
        )
        return reference, [
            EventDraft(
                uuid4(),
                definition_facts.EVENT_TYPE,
                1,
                "domain",
                item.domain_id,
                reference,
                payload.model_dump(mode="json"),
                command.request_id,
            )
        ]

    async def _associated(
        self,
        connection: AsyncConnection,
        item: IntakeItem,
        command: IntakeAction,
        actor: Ref,
        request: UUID,
        body: RichContent,
    ) -> tuple[Ref, Ref | None, list[EventDraft], facts.InstanceVersion | None]:
        checks = [command.classification_check_ref] if command.classification_check_ref else []
        if item.kind == "task_instance" and command.action == "associate_task" and command.task_ref:
            task = command.task_ref
            await require_definition(connection, item.domain_id, task)
            await self.analysis.require_match(
                connection,
                item.domain_id,
                item,
                command.classification_check_ref,
                [definition_facts.version_ref(task)],
            )
            reused = command.existing_instance_ref
            if reused is not None:
                existing = await load_instance(
                    connection, item.domain_id, reused.object_id, reused.version
                )
                active = await load_instance(connection, item.domain_id, reused.object_id)
                if (
                    active.is_deleted
                    or existing.is_deleted
                    or existing.content.task_ref != task
                    or existing.content.statement.blocks != body.blocks
                    or existing.content.statement.data_tables != body.data_tables
                ):
                    raise RequestError(409, "classification_failed", "已有实例与本题内容不一致。")
                return reused.reference(), None, [], None
            new = TaskInstance(
                title=item.title,
                task_ref=task,
                statement=body,
                answer_basis=None,
                reference_solutions=[],
                source_refs=body.source_refs,
            )
            draft, value = instance_event(
                item.domain_id,
                uuid5(request, "instance"),
                None,
                new,
                actor,
                request,
                "采用教材题目",
                "create",
                checks,
            )
            return draft.owner_ref, None, [draft], value
        if (
            item.kind != "reference"
            or command.action != "associate_solution"
            or not command.solution_ref
        ):
            raise RequestError(400, "invalid_request", "请为所选待办指定对应领域定义。")
        parent = await self.parent_instance(connection, item)
        if (
            command.task_instance_ref != parent.instance_ref
            or command.expected_version != parent.instance_ref.version
        ):
            raise RequestError(409, "version_conflict", "题目版本已变化，请刷新后关联。")
        solution = command.solution_ref
        await require_definition(connection, item.domain_id, solution)
        task = parent.content.task_ref
        current_task = TaskDefinition.model_validate(
            await require_definition(connection, item.domain_id, task)
        )
        adding_method = solution not in current_task.method_refs
        await self.analysis.require_match(
            connection,
            item.domain_id,
            item,
            command.classification_check_ref,
            [definition_facts.version_ref(task), definition_facts.version_ref(solution)],
            adding_method=adding_method,
            parent_statement=parent.content.statement.model_dump(mode="json"),
        )
        drafts: list[EventDraft] = []
        if adding_method:
            if not command.confirm_add_method or command.expected_task_version != task.version:
                raise RequestError(409, "confirmation_required", "请确认将该方法添加到本题任务。")
            head = await connection.scalar(
                text("SELECT head_version FROM domain.object_identity WHERE object_id=:id"),
                {"id": task.object_id},
            )
            if head != task.version:
                raise RequestError(409, "version_conflict", "任务定义已更新，需重新核对方法。")
            added, task = self._add_method(
                item.domain_id,
                task,
                current_task,
                solution,
                actor,
                request,
                command.request_id,
            )
            drafts.append(added)
        reference_id = uuid5(request, "reference")
        reference = ReferenceSolution(
            reference_id=reference_id,
            solution_ref=solution,
            content=body,
            origin="textbook",
            source_refs=body.source_refs,
        )
        updated = parent.content.model_copy(
            update={
                "task_ref": task,
                "reference_solutions": [*parent.content.reference_solutions, reference],
            }
        )
        draft, value = instance_event(
            item.domain_id,
            parent.instance_ref.object_id,
            parent.instance_ref,
            updated,
            actor,
            request,
            "添加教材原有解法",
            "update",
            checks,
        )
        return (
            draft.owner_ref,
            draft.owner_ref.model_copy(update={"path": f"/references/{reference_id}"}),
            [*drafts, draft],
            value,
        )

    @staticmethod
    def _add_method(
        domain: UUID,
        task: TaskRef,
        definition: TaskDefinition,
        method: SolutionRef,
        actor: Ref,
        request: UUID,
        request_id: str,
    ) -> tuple[EventDraft, TaskRef]:
        ref = task.model_copy(update={"version": task.version + 1})
        version = definition_facts.DomainVersion(
            object_id=ref.object_id,
            version=ref.version,
            content_schema_version=1,
            content=definition.model_copy(
                update={"method_refs": [*definition.method_refs, method]}
            ),
            is_deleted=False,
            created_at=datetime.now(UTC),
            created_by=actor,
            change_note="采用教材题内参考时确认补充方法",
        )
        payload = definition_facts.DomainSaved(
            object_ref=ref,
            previous_ref=task,
            action="update",
            request_ref=request,
            records=[
                _record(
                    definition_facts.RECORD_TYPE,
                    definition_facts.RECORD_ID,
                    version.model_dump(mode="json"),
                )
            ],
        )
        return EventDraft(
            uuid4(),
            definition_facts.EVENT_TYPE,
            1,
            "domain",
            domain,
            definition_facts.version_ref(ref),
            payload.model_dump(mode="json"),
            request_id,
        ), ref

    async def parent_instance(self, connection: AsyncConnection, item: IntakeItem) -> InstanceView:
        reference = item.parent_instance_ref
        if reference is None and item.parent_item_id is not None:
            pending = await self.intake.item(connection, item.domain_id, item.parent_item_id)
            if pending.state == "completed":
                reference = pending.result_ref
        if reference is None or reference.type != "task_instance":
            raise RequestError(409, "parent_not_linked", "请先把父题关联到领域。")
        parent = await load_instance(connection, item.domain_id, UUID(reference.id))
        if parent.is_deleted:
            raise RequestError(409, "parent_not_linked", "父题已移除。")
        return parent

    async def read_parent(self, domain_id: UUID, item_id: UUID) -> InstanceView:
        async with self.engine.connect() as connection:
            item = await self.intake.item(connection, domain_id, item_id)
            return await self.parent_instance(connection, item)

    async def _plan(
        self,
        connection: AsyncConnection,
        item: IntakeItem,
        command: IntakeAction,
        actor: Ref,
        request: UUID,
        body: RichContent | None,
    ) -> Plan:
        if item.state != "pending" or item.revision != command.expected_revision:
            raise RequestError(409, "already_processed", "待办状态已更新，请刷新。")
        children: list[IntakeItem] = []
        drafts: list[EventDraft] = []
        root: Ref | None = None
        reference: Ref | None = None
        version: facts.InstanceVersion | None = None
        if command.action == "discard":
            children = await self._children(connection, item.item_id)
            if children and not command.confirm_discard_children:
                raise RequestError(
                    409, "confirmation_required", "此题仍有待办解法，请确认一起移除。"
                )
        elif command.action == "add_kc":
            root, drafts = await self._knowledge(connection, item, command, actor, request)
        else:
            assert body is not None
            root, reference, drafts, version = await self._associated(
                connection, item, command, actor, request, body
            )
        affected = [
            entry.model_copy(
                update={
                    "state": "removed" if command.action == "discard" else "completed",
                    "result_ref": root,
                    "revision": entry.revision + 1,
                    "processed_request_ref": request,
                }
            )
            for entry in [item, *children]
        ]
        pending_count = await connection.scalar(
            text(
                "SELECT count(*) FROM domain.intake_item WHERE group_id=:group AND state='pending' "
                "AND NOT(item_id=ANY(CAST(:affected AS uuid[])))"
            ),
            {"group": item.group_id, "affected": [entry.item_id for entry in affected]},
        )
        result = IntakeActionResult(
            item_ref=affected[0].reference(),
            state="discarded"
            if command.action == "discard"
            else "added"
            if command.action == "add_kc"
            else "associated",
            object_ref=root,
            reference_ref=reference,
            check_refs=[command.classification_check_ref]
            if command.classification_check_ref
            else [],
            affected_item_refs=[entry.reference() for entry in affected],
            group_pending_count=pending_count,
        )
        payload = facts.ItemProcessed(
            domain_id=item.domain_id,
            request_ref=request,
            result=result,
            records=[
                _record(ITEM, str(entry.item_id), entry.model_dump(mode="json"))
                for entry in affected
            ],
        )
        drafts.append(
            EventDraft(
                uuid4(),
                facts.PROCESSED,
                1,
                "domain",
                item.domain_id,
                result.item_ref,
                payload.model_dump(mode="json"),
                command.request_id,
            )
        )
        return Plan(result, drafts, version)

    async def process(
        self,
        domain_id: UUID,
        item_id: UUID,
        principal: UUID,
        command: IntakeAction,
    ) -> IntakeActionReceipt:
        identity = uuid5(domain_id, f"{PROCESS_INTAKE}:{principal}:{command.request_id}")
        normalized = {**command.model_dump(mode="json"), "item_id": str(item_id)}
        signature = digest(normalized)
        actor = Ref(owner="product", type="account", id=str(principal))
        async with self.engine.connect() as connection:
            previous = (
                await connection.execute(
                    text(
                        "SELECT input_hash,result_ref FROM domain.command_receipt "
                        "WHERE receipt_id=:id"
                    ),
                    {"id": identity},
                )
            ).one_or_none()
            if previous:
                if previous.input_hash != signature:
                    raise RequestError(409, "request_conflict", "此编号已用于另一项处理。")
                return IntakeActionReceipt(
                    request_ref=identity,
                    result=await self._result(domain_id, UUID(previous.result_ref["id"])),
                )
            item = await self.intake.item(connection, domain_id, item_id)
        body = None
        if command.action in ("associate_task", "associate_solution"):
            raw = await self.intake.candidate(item)
            content = raw["body"]
            assert isinstance(content, dict)
            body = RichContent.model_validate_json(canonical_json(content["content"]))
        async with self.engine.connect() as connection:
            plan = await self._plan(connection, item, command, actor, identity, body)
        scope = ("domain", domain_id)
        access = ProducerAccess("domain", actor, frozenset({scope}))
        prepared = await self.analysis.attachments.prepare(
            self.intake.store,
            access,
            tuple(plan.drafts),
        )
        async with self.engine.begin() as connection:
            inserted = await connection.scalar(
                text(
                    "INSERT INTO domain.command_receipt "
                    "(receipt_id,principal_id,action,scope_id,request_id,normalized_input,input_hash,"
                    "state,created_at,updated_at) VALUES "
                    "(:id,:owner,:action,:domain,:request,CAST(:input AS jsonb),:hash,"
                    "'accepted',clock_timestamp(),clock_timestamp()) "
                    "ON CONFLICT (principal_id,action,scope_id,request_id) "
                    "DO NOTHING RETURNING receipt_id"
                ),
                {
                    "id": identity,
                    "owner": str(principal),
                    "action": PROCESS_INTAKE,
                    "domain": str(domain_id),
                    "request": command.request_id,
                    "input": canonical_json(normalized),
                    "hash": signature,
                },
            )
            if inserted is None:
                row = (
                    await connection.execute(
                        text(
                            "SELECT input_hash,result_ref FROM domain.command_receipt "
                            "WHERE receipt_id=:id"
                        ),
                        {"id": identity},
                    )
                ).one()
                if row.input_hash != signature:
                    raise RequestError(409, "request_conflict", "此编号已用于另一项处理。")
                result = await self._result(domain_id, UUID(row.result_ref["id"]))
                return IntakeActionReceipt(request_ref=identity, result=result)
            if command.action != "discard":
                await self.analysis.guard_source(
                    connection, UUID(item.candidate_key.partition(":")[0]), item.source_ref
                )
            await self.analysis.lock(connection, "domain", domain_id)
            locked = await self.intake.item(connection, domain_id, item_id)
            checked = await self._plan(connection, locked, command, actor, identity, body)
            if checked.result != plan.result:
                raise RequestError(409, "version_conflict", "待办或题目已变化，请重试。")
            if checked.instance_version and plan.instance_version:
                if checked.instance_version.content != plan.instance_version.content:
                    raise RequestError(409, "version_conflict", "题目内容已变化，请重试。")
            sequence = await lock_scope_sequence(connection, *scope)
            events = await self.intake.store.append(
                connection,
                access,
                prepared,
                commit_id=uuid4(),
                correlation_id=identity,
                expected_seq={scope: sequence},
            )
            for event in events:
                if event.draft.event_type == facts.PROCESSED:
                    await facts.project_items(connection, event)
                elif event.draft.event_type == facts.SAVED:
                    assert plan.instance_version is not None
                    await validate_instance(connection, domain_id, plan.instance_version.content)
                    await facts.project_instance(connection, event, plan.instance_version)
                else:
                    await apply_domain_event(connection, event)
            result_ref = Ref(owner="runtime", type="event", id=str(events[-1].draft.event_id))
            await connection.execute(
                text(
                    "UPDATE domain.command_receipt SET state='completed',"
                    "result_ref=CAST(:result AS jsonb),"
                    "updated_at=clock_timestamp() WHERE receipt_id=:id"
                ),
                {"id": identity, "result": result_ref.model_dump_json()},
            )
        return IntakeActionReceipt(request_ref=identity, result=plan.result)

    async def receipt(
        self,
        principal: UUID,
        _session: UUID,
        query: ReceiptQuery,
    ) -> ReceiptView[IntakeActionResult]:
        domain = query.resource_id
        identity = uuid5(domain, f"{PROCESS_INTAKE}:{principal}:{query.request_id}")
        async with self.engine.connect() as connection:
            result = await connection.scalar(
                text(
                    "SELECT result_ref FROM domain.command_receipt "
                    "WHERE receipt_id=:id AND state='completed'"
                ),
                {"id": identity},
            )
        if result is None:
            return ReceiptView[IntakeActionResult](receipt_state="not_found")
        return ReceiptView[IntakeActionResult](
            receipt_state="completed",
            receipt_ref=identity,
            result=await self._result(domain, UUID(result["id"])),
        )
