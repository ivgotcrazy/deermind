"""Save course goals against the adopted textbook and immutable Claim definitions."""

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from deermind.abstractions.command_receipts import CommandReceipt
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import EventDraft, FactRecord, InlineContent, ProducerAccess, Ref
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.public.errors import Issue, RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.learning import target_facts as facts
from deermind.product.learning.requirements import ConditionResolver, prepare_item
from deermind.product.materials.chapter_associations import AssociationFact
from deermind.product.materials.receiving import MaterialReceiving, cursor_position
from deermind.product.persistence.receipts import (
    claim_request,
    complete_request,
    find_completed_request,
)
from deermind.product.public.chapter_associations import ChapterAssociationView
from deermind.product.public.learning_targets import (
    SAVE_TARGET,
    GoalItem,
    GoalItemFields,
    ReviseTarget,
    TargetCommand,
    TargetDetail,
    TargetList,
    TargetReceipt,
    TargetRef,
)
from deermind.spaces.evaluation.public import ClaimDetail, ClaimRef, ClaimView
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

type ClaimReader = Callable[[UUID, int | None], Awaitable[ClaimDetail]]


class TargetDefinitions:
    def __init__(
        self, materials: MaterialReceiving, claims: ClaimReader, resolve: ConditionResolver
    ) -> None:
        self.materials = materials
        self.engine = materials.engine
        self.claims = claims
        self.resolve = resolve

    async def _book(self, db: AsyncConnection, textbook: UUID, *, lock: bool = False) -> UUID:
        row = (
            await db.execute(
                text("SELECT import_id,domain_id FROM product.textbook WHERE textbook_id=:id"),
                {"id": textbook},
            )
        ).one_or_none()
        if row is None:
            raise RequestError(404, "not_found", "找不到此教材。")
        await self.materials.read_import(db, row.import_id, lock=lock)
        return row.domain_id

    async def chapter_basis(
        self, db: AsyncConnection, book: UUID, item: GoalItemFields, claim: ClaimView
    ) -> dict[UUID, ChapterAssociationView]:
        task = claim.definition.task_ref
        rows = (
            await db.execute(
                text(
                    "SELECT chapter_id,to_jsonb(a)-'source_event_id' AS body "
                    "FROM product.chapter_association a WHERE textbook_id=:book "
                    "AND chapter_id=ANY(:chapters) AND active "
                    "AND task_id=:task AND task_version=:version"
                ),
                {
                    "book": book,
                    "chapters": item.chapter_refs,
                    "task": task.object_id,
                    "version": task.version,
                },
            )
        ).all()
        return {
            row.chapter_id: AssociationFact.model_validate_json(canonical_json(row.body)).view()
            for row in rows
        }

    async def _build(
        self,
        db: AsyncConnection,
        body: TargetCommand,
        claims: Mapping[ClaimRef, ClaimView],
        prior: set[UUID],
    ) -> tuple[list[GoalItem], list[Issue], list[Ref]]:
        items: list[GoalItem] = []
        gaps: list[Issue] = []
        refs: dict[str, Ref] = {}
        seen: set[UUID] = set()
        for index, draft in enumerate(body.items):
            if draft.item_id in seen:
                raise RequestError(400, "invalid_reference", "目标项不能重复。")
            claim = claims[draft.claim_ref]
            chapters = await self.chapter_basis(db, body.textbook_id, draft, claim)
            item, missing, sources = prepare_item(
                draft, claim, chapters, prior, f"/items/{index}", self.resolve
            )
            items.append(item)
            gaps.extend(missing)
            refs.update((ref.id, ref) for ref in sources)
            seen.add(item.item_id)
        return items, gaps, list(refs.values())

    async def detail(self, target_id: UUID, revision: int | None) -> TargetDetail:
        async with self.engine.connect() as db:
            row = (
                await db.execute(
                    text(
                        "SELECT h.textbook_id,v.source_event_id FROM product.learning_target h "
                        "JOIN product.learning_target_version v USING(target_id) "
                        "WHERE h.target_id=:id AND v.revision=COALESCE(:revision,h.head_revision)"
                    ),
                    {"id": target_id, "revision": revision},
                )
            ).one_or_none()
        if row is None:
            raise RequestError(404, "not_found", "找不到此学习目标修订。")
        result = await self.materials.reader.read_facts(
            "learning_target",
            target_id,
            row.source_event_id,
            expected_event_type=facts.EVENT,
            refs=[EventPartRef(event_id=row.source_event_id, record_id=str(target_id), path="")],
        )
        parts = result["items"]
        assert isinstance(parts, list) and isinstance(parts[0], dict)
        snapshot = facts.TargetVersion.model_validate_json(canonical_json(parts[0]["content"]))
        return TargetDetail(target=snapshot.as_view(row.textbook_id))

    async def list_targets(
        self, principal: UUID, textbook_id: UUID, cursor: str | None, limit: int
    ) -> TargetList:
        token = sha256(f"{principal}:{textbook_id}:targets".encode()).hexdigest()
        after = cursor_position(cursor, token)
        async with self.engine.connect() as db:
            await self._book(db, textbook_id)
            rows = (
                await db.execute(
                    text(
                        "SELECT target_id,head_revision FROM product.learning_target "
                        "WHERE textbook_id=:book AND "
                        "(CAST(:after AS uuid) IS NULL OR target_id>:after) "
                        "ORDER BY target_id LIMIT :limit"
                    ),
                    {"book": textbook_id, "after": after, "limit": limit + 1},
                )
            ).all()
        return TargetList(
            items=[
                (await self.detail(row.target_id, row.head_revision)).target for row in rows[:limit]
            ],
            next_cursor=f"{token}.{rows[limit - 1].target_id}" if len(rows) > limit else None,
        )

    async def _replay(self, saved: CommandReceipt) -> TargetReceipt:
        ref = saved.result_ref
        assert ref is not None and ref.revision is not None
        return TargetReceipt(
            request_ref=saved.request_ref, result=await self.detail(UUID(ref.id), ref.revision)
        )

    async def receipt(
        self, principal: UUID, _session: UUID, query: ReceiptQuery
    ) -> ReceiptView[TargetDetail]:
        async with self.engine.connect() as db:
            saved = await find_completed_request(
                db, principal, SAVE_TARGET, query.resource_id, query.request_id
            )
        if saved is None:
            return ReceiptView[TargetDetail](receipt_state="not_found")
        reply = await self._replay(saved)
        return ReceiptView[TargetDetail](
            receipt_state="completed", receipt_ref=reply.request_ref, result=reply.result
        )

    async def save(self, principal: UUID, body: TargetCommand) -> TargetReceipt:
        normalized = body.model_dump(mode="json")
        book = body.textbook_id
        async with self.engine.connect() as db:
            saved = await find_completed_request(
                db, principal, SAVE_TARGET, book, body.request_id, normalized
            )
            domain = await self._book(db, book)
        if saved is not None:
            return await self._replay(saved)
        target_id = body.target_id if isinstance(body, ReviseTarget) else uuid4()
        expected = body.expected_revision if isinstance(body, ReviseTarget) else None
        prior_items: set[UUID] = set()
        if expected is not None:
            previous = (await self.detail(target_id, expected)).target
            if previous.textbook_id != book:
                raise RequestError(404, "not_found", "找不到此教材的学习目标。")
            prior_items = {item.item_id for item in previous.items}
        claims: dict[ClaimRef, ClaimView] = {}
        for item in body.items:
            ref = item.claim_ref
            if ref not in claims:
                claim = (await self.claims(ref.claim_id, ref.revision)).claim
                if claim.definition.domain_id != domain:
                    raise RequestError(409, "invalid_reference", "Claim 不属于该教材领域。")
                claims[ref] = claim
        async with self.engine.connect() as db:
            items, gaps, chapter_refs = await self._build(db, body, claims, prior_items)
        now = datetime.now(UTC)
        revision = (expected or 0) + 1
        actor = Ref(owner="product", type="account", id=str(principal))
        target_ref = TargetRef(target_id=target_id, revision=revision)
        reference = Ref(
            owner="product", type="learning_target", id=str(target_id), revision=revision
        )
        scope = ("learning_target", target_id)
        access = ProducerAccess("product", actor, frozenset({scope}))
        request = uuid4()
        head = facts.TargetHead(
            target_id=target_id, textbook_id=book, head_revision=revision, created_at=now
        )
        snapshot = facts.TargetVersion(
            target_id=target_id,
            revision=revision,
            title=body.title,
            items=items,
            chapter_basis=chapter_refs,
            gaps=gaps,
            actor_ref=actor,
            created_at=now,
        )
        change = facts.LearningTargetSaved(
            target_ref=target_ref,
            previous_target_ref=(
                TargetRef(target_id=target_id, revision=expected) if expected is not None else None
            ),
            textbook_id=book,
            request_ref=request,
            records=[
                FactRecord(
                    record_id=str(target_id) if kind == facts.VERSION else f"{target_id}-head",
                    record_type=kind,
                    schema_version=1,
                    content=InlineContent(storage="inline", value=value.model_dump(mode="json")),
                )
                for kind, value in ((facts.HEAD, head), (facts.VERSION, snapshot))
            ],
        )
        draft = EventDraft(
            uuid4(),
            facts.EVENT,
            1,
            *scope,
            reference,
            change.model_dump(mode="json"),
            body.request_id,
        )
        prepared = await self.materials.attachments.prepare(self.materials.events, access, (draft,))
        async with self.engine.begin() as db:
            receipt = await claim_request(
                db,
                principal_id=str(principal),
                action=SAVE_TARGET,
                scope_id=str(book),
                request_id=body.request_id,
                normalized_input=normalized,
                reserved_ref=request,
            )
            if receipt.result_ref is None:
                await self._book(db, book, lock=True)
                current = (
                    await db.execute(
                        text(
                            "SELECT head_revision FROM product.learning_target "
                            "WHERE target_id=:id FOR UPDATE"
                        ),
                        {"id": target_id},
                    )
                ).one_or_none()
                if expected != (current.head_revision if current else None):
                    raise RequestError(409, "revision_conflict", "学习目标已变化，请重新读取。")
                for item in items:
                    chapters = await self.chapter_basis(db, book, item, claims[item.claim_ref])
                    if len(chapters) != len(item.chapter_refs) or any(
                        value.association_ref not in chapter_refs for value in chapters.values()
                    ):
                        raise RequestError(409, "revision_conflict", "章节关联已变化，请重新选择。")
                sequence = await lock_scope_sequence(db, *scope)
                (stored,) = await self.materials.events.append(
                    db,
                    access,
                    prepared,
                    commit_id=uuid4(),
                    correlation_id=request,
                    expected_seq={scope: sequence},
                )
                await facts.project(db, stored)
                await complete_request(db, receipt, reference)
                return TargetReceipt(
                    request_ref=request, result=TargetDetail(target=snapshot.as_view(book))
                )
        return await self._replay(receipt)
