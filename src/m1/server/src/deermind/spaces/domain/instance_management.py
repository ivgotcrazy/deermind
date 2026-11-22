"""题目的可追溯新版本、原收据和软删除。"""

from uuid import UUID, uuid4, uuid5

from sqlalchemy import text

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import ProducerAccess, Ref
from deermind.abstractions.hashing import digest
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.spaces.domain.analysis import DomainAnalysis
from deermind.spaces.domain.instance_facts import project_instance
from deermind.spaces.domain.instances import instance_event, load_instance, validate_instance
from deermind.spaces.domain.public import (
    SAVE_INSTANCE,
    InstanceCommand,
    InstanceList,
    InstanceReceipt,
    InstanceView,
    TaskInstance,
)


class InstanceManagement:
    def __init__(self, analysis: DomainAnalysis) -> None:
        self.analysis = analysis
        self.engine = analysis.engine

    async def read(self, domain_id: UUID, identity: UUID, version: int | None) -> InstanceView:
        async with self.engine.connect() as connection:
            result = await load_instance(connection, domain_id, identity, version)
        if version is None and result.is_deleted:
            raise RequestError(404, "not_found", "题目已移除。")
        return result

    async def list_instances(self, domain_id: UUID, cursor: str | None, limit: int) -> InstanceList:
        try:
            after = UUID(cursor) if cursor else None
        except ValueError as error:
            raise RequestError(400, "invalid_request", "题目列表的续页位置无效。") from error
        async with self.engine.connect() as connection:
            ids = (
                await connection.scalars(
                    text(
                        "SELECT i.object_id FROM domain.object_identity i "
                        "JOIN domain.object_version h "
                        "ON (h.object_id,h.version)=(i.object_id,i.head_version) "
                        "WHERE i.domain_id=:domain AND i.kind='task_instance' AND NOT h.is_deleted "
                        "AND (CAST(:after AS uuid) IS NULL OR i.object_id>:after) "
                        "ORDER BY i.object_id LIMIT :limit"
                    ),
                    {"domain": domain_id, "after": after, "limit": limit + 1},
                )
            ).all()
            items = [
                await load_instance(connection, domain_id, identity) for identity in ids[:limit]
            ]
        return InstanceList(
            items=items,
            next_cursor=str(ids[limit - 1]) if len(ids) > limit else None,
        )

    @staticmethod
    def _content(command: InstanceCommand, previous: InstanceView | None) -> TaskInstance:
        if command.action == "soft_delete":
            if previous is None or command.instance is not None:
                raise RequestError(400, "invalid_request", "请选择要移除的题目。")
            return previous.content
        instance = command.instance
        if instance is None:
            raise RequestError(400, "invalid_request", "请提供完整题目。")
        original = previous.content if previous else None
        references = (
            {item.reference_id: item for item in original.reference_solutions} if original else {}
        )
        for entry in instance.reference_solutions:
            if entry.origin != "admin_authored" and references.get(entry.reference_id) != entry:
                raise RequestError(400, "invalid_reference", "教材或系统原有解法需沿原流程提交。")
            if entry.origin == "admin_authored" and (
                entry.source_refs or entry.content.source_refs
            ):
                raise RequestError(400, "invalid_reference", "手工解法不得直接引用未经核对的来源。")
        if (instance.source_refs or instance.statement.source_refs) and (
            original is None
            or instance.source_refs != original.source_refs
            or instance.statement.source_refs != original.statement.source_refs
        ):
            raise RequestError(400, "invalid_reference", "手工修改不能增加未经核对的教材来源。")
        return instance

    async def save(
        self,
        domain_id: UUID,
        principal: UUID,
        command: InstanceCommand,
    ) -> InstanceReceipt:
        request = uuid5(domain_id, f"{SAVE_INSTANCE}:{principal}:{command.request_id}")
        body = command.model_dump(mode="json")
        signature = digest(body)
        store = self.analysis.event_store
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT input_hash,result_ref FROM domain.command_receipt "
                        "WHERE receipt_id=:id"
                    ),
                    {"id": request},
                )
            ).one_or_none()
            if row is not None:
                if row.input_hash != signature:
                    raise RequestError(409, "request_conflict", "此编号已用于另一题目修改。")
                ref = Ref.model_validate(row.result_ref)
                saved = await load_instance(connection, domain_id, UUID(ref.id), ref.version)
                return InstanceReceipt(request_ref=request, result=saved)
            previous = None
            if command.object_ref is not None:
                previous = await load_instance(connection, domain_id, command.object_ref.object_id)
        if command.action == "create":
            if command.object_ref is not None or command.expected_version is not None:
                raise RequestError(400, "invalid_reference", "新题目无需指定旧版本。")
        elif (
            previous is None
            or previous.is_deleted
            or command.object_ref != previous.instance_ref
            or command.expected_version != previous.instance_ref.version
        ):
            raise RequestError(409, "version_conflict", "题目已更新，请重新读取。")
        content = self._content(command, previous)
        reference = previous.instance_ref if previous else None
        identity = reference.object_id if reference else uuid5(request, "new-instance")
        actor = Ref(owner="product", type="account", id=str(principal))
        checks = [command.classification_check_ref] if command.classification_check_ref else []
        draft, value = instance_event(
            domain_id,
            identity,
            reference,
            content,
            actor,
            request,
            command.change_note,
            command.action,
            checks,
        )
        scope = ("domain", domain_id)
        access = ProducerAccess("domain", actor, frozenset({scope}))
        prepared = await self.analysis.attachments.prepare(store, access, (draft,))
        async with self.engine.begin() as connection:
            claimed = await connection.scalar(
                text(
                    "INSERT INTO domain.command_receipt "
                    "(receipt_id,principal_id,action,scope_id,request_id,normalized_input,input_hash,"
                    "state,created_at,updated_at) VALUES "
                    "(:id,:actor,:action,:scope,:request,CAST(:body AS jsonb),:hash,"
                    "'accepted',clock_timestamp(),clock_timestamp()) "
                    "ON CONFLICT(principal_id,action,scope_id,request_id) "
                    "DO NOTHING RETURNING receipt_id"
                ),
                {
                    "id": request,
                    "actor": str(principal),
                    "action": SAVE_INSTANCE,
                    "scope": str(domain_id),
                    "request": command.request_id,
                    "body": canonical_json(body),
                    "hash": signature,
                },
            )
            if claimed is None:
                row = (
                    await connection.execute(
                        text(
                            "SELECT input_hash,result_ref FROM domain.command_receipt "
                            "WHERE receipt_id=:id"
                        ),
                        {"id": request},
                    )
                ).one()
                if row.input_hash != signature:
                    raise RequestError(409, "request_conflict", "此编号已用于另一题目修改。")
                ref = Ref.model_validate(row.result_ref)
                result = await load_instance(connection, domain_id, UUID(ref.id), ref.version)
                return InstanceReceipt(request_ref=request, result=result)
            await self.analysis.lock(connection, *scope)
            if reference is not None:
                current = await load_instance(connection, domain_id, identity)
                if current.instance_ref != reference or current.is_deleted:
                    raise RequestError(409, "version_conflict", "题目已更新，请重新读取。")
            if command.action != "soft_delete":
                await validate_instance(connection, domain_id, content)
                if previous is None or previous.content != content:
                    await self.analysis.require_instance_match(
                        connection,
                        domain_id,
                        content,
                        command.classification_check_ref,
                    )
            sequence = await lock_scope_sequence(connection, *scope)
            (event,) = await store.append(
                connection,
                access,
                prepared,
                commit_id=uuid4(),
                correlation_id=request,
                expected_seq={scope: sequence},
            )
            await project_instance(connection, event, value)
            await connection.execute(
                text(
                    "UPDATE domain.command_receipt SET state='completed',"
                    "result_ref=CAST(:result AS jsonb),updated_at=clock_timestamp() "
                    "WHERE receipt_id=:id"
                ),
                {"id": request, "result": draft.owner_ref.model_dump_json()},
            )
            result = await load_instance(connection, domain_id, identity, value.version)
        return InstanceReceipt(request_ref=request, result=result)

    async def receipt(
        self,
        principal: UUID,
        _session: UUID,
        query: ReceiptQuery,
    ) -> ReceiptView[InstanceView]:
        domain = query.resource_id
        identity = uuid5(domain, f"{SAVE_INSTANCE}:{principal}:{query.request_id}")
        async with self.engine.connect() as connection:
            row = await connection.scalar(
                text(
                    "SELECT result_ref FROM domain.command_receipt "
                    "WHERE receipt_id=:id AND state='completed'"
                ),
                {"id": identity},
            )
            if row is None:
                return ReceiptView[InstanceView](receipt_state="not_found")
            ref = Ref.model_validate(row)
            saved = await load_instance(connection, domain, UUID(ref.id), ref.version)
        return ReceiptView[InstanceView](
            receipt_state="completed", receipt_ref=identity, result=saved
        )
