"""Read the selected course inputs and persist a reviewed, immutable check."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import ProducerAccess, Ref
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.learning import course_facts as facts
from deermind.product.learning.readiness import MethodCheck, issue, prepare_course
from deermind.product.learning.targets import TargetDefinitions
from deermind.product.materials.chapter_associations import AssociationFact
from deermind.product.persistence.receipts import (
    claim_request,
    complete_request,
    find_completed_request,
)
from deermind.product.public.courses import (
    CHECK_COURSE,
    ApplicationHead,
    ChapterSelection,
    ChapterSnapshot,
    CourseCheckCommand,
    CourseCheckReceipt,
    CourseCheckResult,
)
from deermind.spaces.interaction.public import ConfigView
from pydantic import TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

type ConfigReader = Callable[[Ref], Awaitable[ConfigView]]
REFS = TypeAdapter(list[Ref])


def view(check: facts.CheckRow) -> CourseCheckResult:
    return CourseCheckResult(
        check_ref=facts.ref("application_check", check.check_id),
        base_application_ref=check.base_application_ref,
        proposed_application=check.proposed_application,
        changes=[
            issue(
                "chapters_selected", "/chapters", f"本次核对 {len(check.input.chapters)} 个章节。"
            )
        ],
        readiness=check.purpose_checks,
        can_apply=not check.blockers,
    )


class CourseChecks:
    def __init__(
        self, targets: TargetDefinitions, configs: ConfigReader, check_methods: MethodCheck
    ) -> None:
        self.targets = targets
        self.materials = targets.materials
        self.engine = targets.engine
        self.configs = configs
        self.check_methods = check_methods

    async def head(self, textbook: UUID, target: UUID) -> ApplicationHead:
        async with self.engine.connect() as db:
            await self.book(db, textbook, lock=False)
            row = (
                await db.execute(
                    text("""
                        SELECT c.application_id, c.revision,
                            c.content_snapshot->'target_ref' AS target_ref
                        FROM product.application_head h
                        JOIN product.course_application c
                            ON c.application_id=h.current_application_ref
                        WHERE h.textbook_id=:book AND h.target_id=:target
                    """),
                    {"book": textbook, "target": target},
                )
            ).one_or_none()
        return ApplicationHead(
            application_ref=facts.ref("course_application", row.application_id) if row else None,
            application_version=row.revision if row else None,
            target_revision=row.target_ref["revision"] if row else None,
        )

    async def book(self, db: AsyncConnection, book: UUID, *, lock: bool) -> tuple[UUID, UUID, str]:
        row = (
            await db.execute(
                text(
                    "SELECT import_id,domain_id,metadata->>'title' AS title "
                    "FROM product.textbook WHERE textbook_id=:id"
                ),
                {"id": book},
            )
        ).one_or_none()
        if row is None:
            raise RequestError(404, "not_found", "找不到教材。")
        await self.materials.read_import(db, row.import_id, lock=lock)
        return row.import_id, row.domain_id, row.title

    async def current(
        self, db: AsyncConnection, textbook: UUID, target: UUID
    ) -> facts.CourseRow | None:
        raw = await db.scalar(
            text(
                "SELECT to_jsonb(a)-'source_event_id'-'revision' FROM product.application_head h "
                "JOIN product.course_application a ON a.application_id=h.current_application_ref "
                "WHERE h.textbook_id=:book AND h.target_id=:target"
            ),
            {"book": textbook, "target": target},
        )
        return None if raw is None else facts.CourseRow.model_validate_json(canonical_json(raw))

    async def fixed_check(self, db: AsyncConnection, reference: Ref) -> facts.CheckRow:
        if reference.owner != "product" or reference.type != "application_check":
            raise RequestError(400, "invalid_reference", "请选择一条课程检查。")
        try:
            identity = UUID(reference.id)
        except ValueError as error:
            raise RequestError(400, "invalid_reference", "课程检查编号无效。") from error
        raw = await db.scalar(
            text(
                "SELECT to_jsonb(c)-'source_event_id' FROM product.application_check c "
                "WHERE check_id=:id"
            ),
            {"id": identity},
        )
        if raw is None:
            raise RequestError(404, "not_found", "找不到课程检查。")
        return facts.CheckRow.model_validate_json(canonical_json(raw))

    async def receipt(
        self, principal: UUID, _session: UUID, query: ReceiptQuery
    ) -> ReceiptView[CourseCheckResult]:
        async with self.engine.connect() as db:
            receipt = await find_completed_request(
                db,
                principal,
                CHECK_COURSE,
                query.resource_id,
                query.request_id,
            )
            if receipt is None or receipt.result_ref is None:
                return ReceiptView[CourseCheckResult](receipt_state="not_found")
            result = view(await self.fixed_check(db, receipt.result_ref))
        return ReceiptView[CourseCheckResult](
            receipt_state="completed",
            receipt_ref=receipt.request_ref,
            result=result,
        )

    async def chapter(
        self,
        db: AsyncConnection,
        textbook: UUID,
        import_id: UUID,
        selection: ChapterSelection,
    ) -> ChapterSnapshot:
        key = {"book": textbook, "id": selection.chapter_id, "import": import_id}
        row = (
            await db.execute(
                text(
                    "SELECT title,revision,page_refs FROM product.material_chapter "
                    "WHERE textbook_id=:book AND chapter_id=:id"
                ),
                key,
            )
        ).one_or_none()
        if row is None or row.revision != selection.revision:
            raise RequestError(409, "check_stale", "选用章节已变化，请重新检查。")
        contents = (
            await db.execute(
                text(
                    "SELECT candidate_id,candidate_revision FROM product.material_content_current "
                    "WHERE import_id=:import AND chapter_id=:id AND validity='current'"
                ),
                key,
            )
        ).all()
        available = [
            facts.ref("material_candidate", item.candidate_id, item.candidate_revision)
            for item in contents
        ]
        canonical = {canonical_json(ref.model_dump(mode="json")) for ref in available}
        given = {canonical_json(ref.model_dump(mode="json")) for ref in selection.content_refs}
        if not given <= canonical or len(given) != len(selection.content_refs):
            raise RequestError(409, "check_stale", "选用的内容已变化，请重新检查。")
        associations = (
            await db.scalars(
                text(
                    "SELECT to_jsonb(a)-'source_event_id' FROM product.chapter_association a "
                    "WHERE textbook_id=:book AND chapter_id=:id AND active ORDER BY association_id"
                ),
                key,
            )
        ).all()
        return ChapterSnapshot(
            title=row.title,
            chapter_id=selection.chapter_id,
            revision=row.revision,
            page_refs=REFS.validate_json(canonical_json(row.page_refs)),
            content_refs=sorted(selection.content_refs, key=lambda ref: ref.id),
            associations=[
                AssociationFact.model_validate_json(canonical_json(body)).view()
                for body in associations
            ],
        )

    async def validate_base(
        self, db: AsyncConnection, command: CourseCheckCommand
    ) -> facts.CourseRow | None:
        current = await self.current(db, command.textbook_id, command.target_ref.target_id)
        ref = facts.ref("course_application", current.application_id) if current else None
        if ref != command.expected_application_ref:
            raise RequestError(409, "check_stale", "当前课程已变化，请重新检查。")
        head = await db.scalar(
            text(
                "SELECT head_revision FROM product.learning_target "
                "WHERE textbook_id=:book AND target_id=:target"
            ),
            {"book": command.textbook_id, "target": command.target_ref.target_id},
        )
        if head != command.target_ref.revision:
            raise RequestError(409, "check_stale", "学习目标已变化，请重新检查。")
        return current

    async def selections(
        self,
        db: AsyncConnection,
        book: UUID,
        import_id: UUID,
        command: CourseCheckCommand,
    ) -> list[ChapterSnapshot]:
        return [await self.chapter(db, book, import_id, entry) for entry in command.chapters]

    async def check(self, principal: UUID, command: CourseCheckCommand) -> CourseCheckReceipt:
        textbook = command.textbook_id
        chapter_ids = {chapter.chapter_id for chapter in command.chapters}
        if len(chapter_ids) != len(command.chapters):
            raise RequestError(400, "invalid_reference", "选用章节不能重复。")
        scope = ("course_application", textbook)
        normalized = command.model_dump(mode="json")
        request = uuid4()
        async with self.engine.connect() as db:
            saved = await find_completed_request(
                db, principal, CHECK_COURSE, textbook, command.request_id, normalized
            )
            if saved is not None and saved.result_ref is not None:
                return CourseCheckReceipt(
                    request_ref=saved.request_ref,
                    result=view(await self.fixed_check(db, saved.result_ref)),
                )
        target = (
            await self.targets.detail(command.target_ref.target_id, command.target_ref.revision)
        ).target
        configs: dict[str, ConfigView] = {}
        for reference in command.activity_config_refs:
            config = await self.configs(reference)
            key = config.definition.activity_type
            if key in configs:
                raise RequestError(400, "invalid_reference", "每类活动只能选用一份配置。")
            configs[key] = config

        async with self.engine.begin() as db:
            import_id, domain, title = await self.book(db, textbook, lock=True)
            old = await self.validate_base(db, command)
            selected = await self.selections(db, textbook, import_id, command)
            chapters = list(selected)
            if old is not None:
                chapters.extend(
                    chapter
                    for chapter in old.content_snapshot.chapters
                    if chapter.chapter_id not in chapter_ids
                )
            snapshot, blockers = await prepare_course(
                db,
                domain,
                title,
                target,
                sorted(chapters, key=lambda row: row.chapter_id),
                configs,
                self.check_methods,
            )

        check = facts.CheckRow(
            check_id=uuid4(),
            request_ref=request,
            base_application_ref=command.expected_application_ref,
            input=command,
            proposed_application=snapshot,
            purpose_checks=snapshot.readiness,
            blockers=blockers,
            created_at=datetime.now(UTC),
        )
        reference = facts.ref("application_check", check.check_id)
        draft = facts.event(
            facts.CHECKED,
            scope,
            reference,
            facts.ApplicationChecked(
                check_ref=reference,
                textbook_id=textbook,
                target_ref=command.target_ref,
                check_status="blocked" if blockers else "ready",
                request_ref=request,
                records=[facts.record(facts.CHECK, check.check_id, check)],
            ),
            request_id=command.request_id,
        )
        access = ProducerAccess("product", facts.ref("account", principal), frozenset({scope}))
        prepared = await self.materials.attachments.prepare(self.materials.events, access, (draft,))
        async with self.engine.begin() as db:
            saved = await claim_request(
                db,
                principal_id=str(principal),
                action=CHECK_COURSE,
                scope_id=str(textbook),
                request_id=command.request_id,
                normalized_input=normalized,
                reserved_ref=request,
            )
            if saved.result_ref is not None:
                return CourseCheckReceipt(
                    request_ref=saved.request_ref,
                    result=view(await self.fixed_check(db, saved.result_ref)),
                )
            import_id, domain, title = await self.book(db, textbook, lock=True)
            await self.validate_base(db, command)
            if title != snapshot.textbook_title or selected != await self.selections(
                db, textbook, import_id, command
            ):
                raise RequestError(409, "check_stale", "本次选用的教材内容已变化。")
            verified, latest_blockers = await prepare_course(
                db, domain, title, target, snapshot.chapters, configs, self.check_methods
            )
            if verified != snapshot or blockers != latest_blockers:
                raise RequestError(409, "check_stale", "课程准备依据已变化，请重新检查。")
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
            await complete_request(db, saved, reference)
        return CourseCheckReceipt(request_ref=request, result=view(check))
