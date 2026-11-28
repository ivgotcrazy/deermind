"""只关闭未完成教材导入及后台工作，保留来源事实和已经入库的领域对象。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    ProducerAccess,
    Ref,
)
from deermind.abstractions.material_intake import DELETED
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.executions import commands, store
from deermind.foundation.system.executions.contracts import Caller
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.materials.assistant import MaterialAssistant
from deermind.product.materials.facts import (
    IMPORT,
    MaterialImportFact,
    OriginalsRemoved,
    project_removal,
    record,
)
from deermind.product.materials.receiving import import_ref
from deermind.product.persistence.receipts import claim_request, complete_request
from deermind.product.public.authentication import SessionView
from deermind.product.public.materials import (
    DELETE_MATERIAL,
    DeleteMaterial,
    MaterialDeletionReceipt,
    MaterialDeletionResult,
)
from sqlalchemy import text


class MaterialDeleted(EventPayload):
    import_id: UUID
    deletion_receipt_ref: Ref
    invalidated_source_refs: list[Ref]
    affected_submission_refs: list[Ref]


def _validate(draft: EventDraft, payload: EventPayload) -> None:
    if (
        not isinstance(payload, MaterialDeleted)
        or payload.import_id != draft.scope_id
        or len(payload.records) != 1
        or payload.records[0].record_type != IMPORT
        or payload.records[0].record_id != str(draft.scope_id)
    ):
        raise ValueError("Deletion must contain one exact import record")


REGISTRATION = EventRegistration(
    DELETED,
    1,
    "product",
    "material_import",
    MaterialDeleted,
    _validate,
    {(IMPORT, 1): MaterialImportFact},
)


class MaterialDeletion:
    def __init__(self, assistant: MaterialAssistant) -> None:
        self.assistant = assistant
        self.materials = assistant.materials

    async def remove_originals(
        self, session: SessionView, identity: UUID, command: DeleteMaterial
    ) -> MaterialDeletionReceipt:
        principal = self.materials.administrator(session)
        scope = ("material_import", identity)
        actor = Ref(owner="product", type="account", id=str(principal))
        async with self.materials.engine.begin() as db:
            receipt = await claim_request(
                db,
                principal_id=str(principal),
                action="product.remove_originals",
                scope_id=str(identity),
                request_id=command.request_id,
                normalized_input=command.model_dump(mode="json"),
            )
            if receipt.result_ref is None:
                row = await self.materials.read_import(db, identity, lock=True)
                expected = Ref(
                    owner="product",
                    type="deletion_scope",
                    id=str(identity),
                    revision=row["revision"],
                )
                if (
                    command.confirmed_scope_ref != expected
                    or command.expected_revision != row["revision"]
                ):
                    raise RequestError(409, "revision_conflict", "教材已变化，请刷新再确认。")
                if row["active_request_ref"] or await db.scalar(
                    text(
                        "SELECT 1 FROM product.material_edition WHERE textbook_id=:book AND "
                        "kind='tree' AND status<>'discarded' LIMIT 1"
                    ),
                    {"book": row["textbook_id"]},
                ):
                    raise RequestError(
                        409, "original_in_use", "原件正在解析或已有内容树版本，无法删除。"
                    )
                sources = list(
                    await db.scalars(
                        text(
                            "SELECT source_id FROM product.material_source WHERE import_id=:id "
                            "ORDER BY source_order"
                        ),
                        {"id": identity},
                    )
                )
                if not sources:
                    raise RequestError(409, "not_found", "教材没有已导入的原件。")
                fact = MaterialImportFact(
                    import_id=identity,
                    textbook_id=row["textbook_id"],
                    status="active",
                    revision=row["revision"] + 1,
                    source_revision=row["source_revision"] + 1,
                    content_revision=row["content_revision"],
                    created_at=row["created_at"],
                    updated_at=datetime.now(UTC),
                )
                payload = OriginalsRemoved(
                    import_id=identity, source_ids=sources, records=[record(IMPORT, identity, fact)]
                )
                event = uuid4()
                access = ProducerAccess("product", actor, frozenset({scope}))
                draft = EventDraft(
                    event,
                    "MaterialOriginalsRemoved",
                    1,
                    *scope,
                    import_ref(identity),
                    payload.model_dump(mode="json"),
                    command.request_id,
                )
                seq = await lock_scope_sequence(db, *scope)
                (stored,) = await self.materials.events.append(
                    db,
                    access,
                    [draft],
                    commit_id=uuid4(),
                    correlation_id=receipt.request_ref,
                    expected_seq={scope: seq},
                )
                await project_removal(db, stored)
                await complete_request(
                    db, receipt, Ref(owner="runtime", type="event", id=str(event))
                )
            return MaterialDeletionReceipt(
                request_ref=receipt.request_ref,
                result=MaterialDeletionResult(import_id=identity, deleted=True),
            )

    async def delete(
        self,
        session: SessionView,
        import_id: UUID,
        command: DeleteMaterial,
    ) -> MaterialDeletionReceipt:
        principal = self.materials.administrator(session)
        actor = Ref(owner="product", type="account", id=str(principal))
        scope = ("material_import", import_id)
        async with self.materials.engine.begin() as connection:
            receipt = await claim_request(
                connection,
                principal_id=str(principal),
                action=DELETE_MATERIAL,
                scope_id=str(import_id),
                request_id=command.request_id,
                normalized_input=command.model_dump(mode="json"),
            )
            if receipt.result_ref is not None:
                # 幂等重放：删除已完成，直接返回成功结果。
                return MaterialDeletionReceipt(
                    request_ref=receipt.request_ref,
                    result=MaterialDeletionResult(import_id=import_id, deleted=True),
                )
            observed = await self.materials.read_import(connection, import_id)
            active = observed["active_request_ref"]
            work = None
            if active is not None:
                # 导入被一轮助手占用，先定位其运行工作。
                work = await connection.scalar(
                    text(
                        "SELECT runtime_ref FROM product.material_turn "
                        "WHERE request_ref=:turn AND import_id=:id"
                    ),
                    {"turn": active, "id": import_id},
                )
                if work is None:
                    # 占用请求缺少持久化运行身份，属内部一致性错误。
                    raise ValueError("Active material work lacks its durable identity")
                # 正常结束和失败收尾都先锁运行工作，再写教材。
                await store.lock_owned(connection, self.assistant.registry, work)

            imported = await self.materials.read_import(connection, import_id, lock=True)
            expected = Ref(
                owner="product",
                type="deletion_scope",
                id=str(import_id),
                revision=imported["revision"],
            )
            if (
                command.expected_revision != imported["revision"]
                or command.confirmed_scope_ref != expected
                or active != imported["active_request_ref"]
            ):
                # 基线版本、删除范围引用或占用状态任一不符即冲突。
                raise RequestError(409, "revision_conflict", "教材已更新，请重新确认删除范围。")
            applied = await connection.scalar(
                text(
                    "SELECT 1 FROM product.learning_space WHERE textbook_id=:book "
                    "UNION ALL SELECT 1 FROM product.material_edition "
                    "WHERE textbook_id=:book AND kind='tree' AND status='published' LIMIT 1"
                ),
                {"book": imported["textbook_id"]},
            )
            if applied is not None:
                # 教材已被课程应用，导入不可删除。
                raise RequestError(
                    409, "already_applied", "教材已有已发布内容树或关联学习空间，无法删除。"
                )
            sources = (
                await connection.scalars(
                    text(
                        "SELECT source_id FROM product.material_source "
                        "WHERE import_id=:id ORDER BY source_order"
                    ),
                    {"id": import_id},
                )
            ).all()
            affected = (
                await connection.scalars(
                    text(
                        "SELECT submission_id FROM product.material_intake_submission "
                        "WHERE import_id=:id AND wait_state='waiting' ORDER BY submission_id"
                    ),
                    {"id": import_id},
                )
            ).all()
            if work is not None:
                # 先取消占用的助手运行，再删除教材。
                await commands.cancel(
                    connection,
                    self.assistant.registry,
                    Caller(actor, "product", frozenset({scope}), frozenset({"cancel"})),
                    work,
                    request_id=command.request_id,
                )
                imported = await self.materials.read_import(connection, import_id)
            version = MaterialImportFact(
                import_id=import_id,
                textbook_id=imported["textbook_id"],
                status="deleted",
                revision=imported["revision"] + 1,
                source_revision=imported["source_revision"],
                content_revision=imported["content_revision"],
                created_at=imported["created_at"],
                updated_at=datetime.now(UTC),
            )
            payload = MaterialDeleted(
                import_id=import_id,
                records=[record(IMPORT, import_id, version)],
                deletion_receipt_ref=Ref(
                    owner="product", type="request", id=str(receipt.request_ref)
                ),
                invalidated_source_refs=[
                    Ref(owner="product", type="material_source", id=str(identity))
                    for identity in sources
                ],
                affected_submission_refs=[
                    Ref(owner="product", type="material_intake_submission", id=str(identity))
                    for identity in affected
                ],
            )
            event_id = uuid4()
            sequence = await lock_scope_sequence(connection, *scope)
            await self.materials.events.append(
                connection,
                ProducerAccess("product", actor, frozenset({scope})),
                [
                    EventDraft(
                        event_id,
                        DELETED,
                        1,
                        *scope,
                        import_ref(import_id),
                        payload.model_dump(mode="json"),
                        command.request_id,
                    )
                ],
                commit_id=uuid4(),
                correlation_id=receipt.request_ref,
                expected_seq={scope: sequence},
            )
            await connection.execute(
                text(
                    "UPDATE product.material_import SET status='deleted',revision=:revision,"
                    "updated_at=:time,source_event_id=:event WHERE import_id=:id"
                ),
                {
                    "id": import_id,
                    "revision": version.revision,
                    "time": version.updated_at,
                    "event": event_id,
                },
            )
            await complete_request(
                connection, receipt, Ref(owner="runtime", type="event", id=str(event_id))
            )
        return MaterialDeletionReceipt(
            request_ref=receipt.request_ref,
            result=MaterialDeletionResult(import_id=import_id, deleted=True),
        )

    async def receipt(
        self,
        principal: UUID,
        _session: UUID,
        query: ReceiptQuery,
    ) -> ReceiptView[MaterialDeletionResult]:
        async with self.materials.engine.connect() as connection:
            identity = await connection.scalar(
                text(
                    "SELECT request_ref FROM product.command_receipt WHERE principal_id=:owner "
                    "AND action=:action AND scope_id=:scope "
                    "AND request_id=:request AND state='completed'"
                ),
                {
                    "owner": str(principal),
                    "action": DELETE_MATERIAL,
                    "scope": str(query.resource_id),
                    "request": query.request_id,
                },
            )
        if identity is None:
            # 无已完成删除收据，按未找到返回。
            return ReceiptView[MaterialDeletionResult](receipt_state="not_found")
        return ReceiptView[MaterialDeletionResult](
            receipt_ref=identity,
            receipt_state="completed",
            result=MaterialDeletionResult(import_id=query.resource_id, deleted=True),
        )
