"""章节选择由Product保存，Domain负责核对Task、Solution及其知识来源。"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    ProducerAccess,
    Ref,
)
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.materials.facts import record
from deermind.product.materials.receiving import MaterialReceiving, cursor_position
from deermind.product.persistence.receipts import claim_request, complete_request
from deermind.product.public.authentication import SessionView
from deermind.product.public.chapter_associations import (
    CHAPTER_ACTION,
    ChapterAssociationCommand,
    ChapterAssociationList,
    ChapterAssociationReceipt,
    ChapterAssociationResult,
    ChapterAssociationView,
)
from deermind.spaces.domain.public import KnowledgeRef, SolutionRef, TaskRef
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

CHANGED = "ChapterAssociationSaved"
RELATION = "product.chapter_association"
type MethodGuard = Callable[
    [AsyncConnection, UUID, TaskRef, list[SolutionRef]], Awaitable[list[KnowledgeRef]]
]


class AssociationFact(FactModel):
    association_id: UUID
    textbook_id: UUID
    chapter_id: UUID
    task_id: UUID
    task_version: int
    method_refs: list[SolutionRef]
    revision: int
    active: bool
    last_event_ref: UUID
    updated_at: datetime

    def view(self) -> ChapterAssociationView:
        return ChapterAssociationView(
            association_ref=Ref(
                owner="product",
                type="chapter_association",
                id=str(self.association_id),
                revision=self.revision,
            ),
            task_ref=TaskRef(kind="task", object_id=self.task_id, version=self.task_version),
            method_refs=self.method_refs,
            active=self.active,
        )


class ChapterChanged(EventPayload):
    textbook_id: UUID
    chapter_id: UUID
    result: ChapterAssociationResult


def _validate(draft: EventDraft, payload: EventPayload) -> None:
    if (
        not isinstance(payload, ChapterChanged)
        or len(payload.records) != 1
        or payload.records[0].record_type != RELATION
        or draft.scope_id != payload.textbook_id
        or payload.records[0].record_id != payload.result.association_ref.id
    ):
        raise ValueError("Invalid chapter association fact")


REGISTRATION = EventRegistration(
    CHANGED,
    1,
    "product",
    "textbook",
    ChapterChanged,
    _validate,
    {(RELATION, 1): AssociationFact},
)


class ChapterAssociations:
    def __init__(self, materials: MaterialReceiving, method_guard: MethodGuard) -> None:
        self.materials = materials
        self.engine = materials.engine
        self.method_guard = method_guard

    async def _context(
        self,
        connection: AsyncConnection,
        book: UUID,
        chapter: UUID,
        *,
        lock: bool = False,
    ) -> tuple[UUID, UUID]:
        row = (
            await connection.execute(
                text(
                    "SELECT t.import_id,t.domain_id FROM product.material_chapter c "
                    "JOIN product.textbook t USING(textbook_id) "
                    "WHERE c.chapter_id=:chapter AND t.textbook_id=:book"
                ),
                {"chapter": chapter, "book": book},
            )
        ).one_or_none()
        if row is None:
            raise RequestError(404, "not_found", "找不到此教材章节。")
        await self.materials.read_import(connection, row.import_id, lock=lock)
        return row.import_id, row.domain_id

    async def list(
        self,
        session: SessionView,
        textbook_id: UUID,
        chapter_id: UUID,
        cursor: str | None,
        limit: int,
    ) -> ChapterAssociationList:
        principal = self.materials.administrator(session)
        from hashlib import sha256

        token = sha256(f"{principal}:{textbook_id}:{chapter_id}".encode()).hexdigest()
        after = cursor_position(cursor, token)
        async with self.engine.connect() as connection:
            await self._context(connection, textbook_id, chapter_id)
            rows = (
                await connection.scalars(
                    text(
                        "SELECT to_jsonb(a)-'source_event_id' FROM product.chapter_association a "
                        "WHERE chapter_id=:chapter AND textbook_id=:book AND active AND "
                        "(CAST(:after AS uuid) IS NULL OR association_id>:after) "
                        "ORDER BY association_id LIMIT :limit"
                    ),
                    {
                        "chapter": chapter_id,
                        "book": textbook_id,
                        "after": after,
                        "limit": limit + 1,
                    },
                )
            ).all()
        selected = [
            AssociationFact.model_validate_json(canonical_json(row)) for row in rows[:limit]
        ]
        return ChapterAssociationList(
            items=[row.view() for row in selected],
            next_cursor=f"{token}.{selected[-1].association_id}" if len(rows) > limit else None,
        )

    async def _read_result(self, book: UUID, event_id: UUID) -> ChapterAssociationResult:
        raw = await self.materials.reader.read_facts(
            "textbook",
            book,
            event_id,
            expected_event_type=CHANGED,
            refs=[EventPartRef(event_id=event_id, record_id=None, path="/result")],
        )
        items = raw["items"]
        assert isinstance(items, list) and isinstance(items[0], dict)
        return ChapterAssociationResult.model_validate_json(canonical_json(items[0]["content"]))

    async def decide(
        self,
        session: SessionView,
        textbook_id: UUID,
        chapter_id: UUID,
        command: ChapterAssociationCommand,
    ) -> ChapterAssociationReceipt:
        principal = self.materials.administrator(session)
        actor = Ref(owner="product", type="account", id=str(principal))
        async with self.engine.begin() as connection:
            receipt = await claim_request(
                connection,
                principal_id=str(principal),
                action=CHAPTER_ACTION,
                scope_id=str(textbook_id),
                request_id=command.request_id,
                normalized_input={**command.model_dump(mode="json"), "chapter_id": str(chapter_id)},
            )
            if receipt.result_ref is not None:
                result = await self._read_result(textbook_id, UUID(receipt.result_ref.id))
                return ChapterAssociationReceipt(request_ref=receipt.request_ref, result=result)
            _import, domain = await self._context(connection, textbook_id, chapter_id, lock=True)
            original = None
            if command.action == "add":
                if command.expected_revision is not None or command.association_id is not None:
                    raise RequestError(400, "invalid_reference", "新增关联不使用旧版本。")
                already = await connection.scalar(
                    text(
                        "SELECT 1 FROM product.chapter_association "
                        "WHERE chapter_id=:chapter AND task_id=:task AND active"
                    ),
                    {"chapter": chapter_id, "task": command.task_ref.object_id},
                )
                if already:
                    raise RequestError(409, "already_linked", "本章已有此任务。")
            else:
                data = await connection.scalar(
                    text(
                        "SELECT to_jsonb(a)-'source_event_id' FROM product.chapter_association a "
                        "WHERE textbook_id=:book AND chapter_id=:chapter "
                        "AND association_id=:id AND active"
                    ),
                    {"book": textbook_id, "chapter": chapter_id, "id": command.association_id},
                )
                if data is not None:
                    original = AssociationFact.model_validate_json(canonical_json(data))
                if (
                    original is None
                    or original.revision != command.expected_revision
                    or original.task_id != command.task_ref.object_id
                ):
                    raise RequestError(409, "revision_conflict", "章节关联已变化，请重新读取。")
            active = command.action != "remove"
            knowledge: list[KnowledgeRef] = []
            methods = command.method_refs
            if active:
                keys = {(method.object_id, method.version) for method in methods}
                if not methods or len(keys) != len(methods):
                    raise RequestError(400, "invalid_reference", "请选择至少一个不同的方法。")
                knowledge = await self.method_guard(connection, domain, command.task_ref, methods)
            else:
                methods = []
            event_id = uuid4()
            association = AssociationFact(
                association_id=original.association_id if original else uuid4(),
                textbook_id=textbook_id,
                chapter_id=chapter_id,
                task_id=command.task_ref.object_id,
                task_version=original.task_version
                if original and not active
                else command.task_ref.version,
                method_refs=methods,
                revision=original.revision + 1 if original else 1,
                active=active,
                last_event_ref=event_id,
                updated_at=datetime.now(UTC),
            )
            result = ChapterAssociationResult(
                **association.view().model_dump(),
                kc_refs=knowledge,
            )
            payload = ChapterChanged(
                textbook_id=textbook_id,
                chapter_id=chapter_id,
                result=result,
                records=[record(RELATION, association.association_id, association)],
            )
            scope = ("textbook", textbook_id)
            sequence = await lock_scope_sequence(connection, *scope)
            await self.materials.events.append(
                connection,
                ProducerAccess("product", actor, frozenset({scope})),
                [
                    EventDraft(
                        event_id,
                        CHANGED,
                        1,
                        *scope,
                        result.association_ref,
                        payload.model_dump(mode="json"),
                        command.request_id,
                    ),
                ],
                commit_id=uuid4(),
                correlation_id=receipt.request_ref,
                expected_seq={scope: sequence},
            )
            await connection.execute(
                text(
                    "INSERT INTO product.chapter_association SELECT * FROM "
                    "jsonb_populate_record(NULL::product.chapter_association,CAST(:row AS jsonb)) "
                    "ON CONFLICT(association_id) DO UPDATE SET task_version=excluded.task_version,"
                    "method_refs=excluded.method_refs,revision=excluded.revision,active=excluded.active,"
                    "updated_at=excluded.updated_at,last_event_ref=excluded.last_event_ref,"
                    "source_event_id=excluded.source_event_id"
                ),
                {
                    "row": canonical_json(
                        {
                            **association.model_dump(mode="json"),
                            "source_event_id": str(event_id),
                        }
                    )
                },
            )
            await complete_request(
                connection, receipt, Ref(owner="runtime", type="event", id=str(event_id))
            )
        return ChapterAssociationReceipt(request_ref=receipt.request_ref, result=result)

    async def receipt(
        self,
        principal: UUID,
        _session: UUID,
        query: ReceiptQuery,
    ) -> ReceiptView[ChapterAssociationResult]:
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT request_ref,result_ref FROM product.command_receipt "
                        "WHERE scope_id=:scope AND principal_id=:owner AND action=:action "
                        "AND request_id=:request AND state='completed'"
                    ),
                    {
                        "scope": str(query.resource_id),
                        "owner": str(principal),
                        "action": CHAPTER_ACTION,
                        "request": query.request_id,
                    },
                )
            ).one_or_none()
        if row is None:
            return ReceiptView[ChapterAssociationResult](receipt_state="not_found")
        return ReceiptView[ChapterAssociationResult](
            receipt_state="completed",
            receipt_ref=row.request_ref,
            result=await self._read_result(query.resource_id, UUID(row.result_ref["id"])),
        )
