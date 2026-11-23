"""Freeze the student's adopted course and append entry/target events."""

from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventFilter, EventPartRef
from deermind.abstractions.events import EventDraft, ProducerAccess, Ref
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.product.learning import course_facts as facts
from deermind.product.learning.course_checks import CourseChecks
from deermind.product.materials.assistant_facts import PROPOSED
from deermind.product.materials.receiving import cursor_position
from deermind.product.persistence.receipts import (
    claim_request,
    complete_request,
    find_completed_request,
)
from deermind.product.public.authentication import AccountView
from deermind.product.public.courses import (
    OPEN_SPACE,
    AdoptionView,
    CourseOption,
    CourseOptions,
    CreateSpace,
    SpaceCommand,
    SpaceGoalView,
    SpaceList,
    SpaceOpenResult,
    SpaceReceipt,
    SpaceRow,
    SpaceWorkspace,
)
from deermind.spaces.evaluation.public import GoalEvaluation
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

type ReadGoal = Callable[[AsyncConnection, UUID, UUID], Awaitable[GoalEvaluation | None]]
CANDIDATE_ORDER = {"kc": 0, "task_instance": 1, "reference": 2}


class CourseSpaces:
    def __init__(self, checks: CourseChecks, read_goal: ReadGoal) -> None:
        self.checks = checks
        self.engine = checks.engine
        self.materials = checks.materials
        self.read_goal = read_goal

    async def current_adoption(self, account: AccountView, space_id: UUID) -> AdoptionView:
        async with self.engine.connect() as db:
            space = await self.row(db, space_id)
            self.authorize(account, space)
            return await self.adopted(db, await self.adoption(db, space.current_adoption_ref))

    async def workspace(self, account: AccountView, space_id: UUID) -> SpaceWorkspace:
        """刷新只读工作区，不登记新的进入事实。"""
        async with self.engine.connect() as db:
            space = await self.row(db, space_id)
            self.authorize(account, space)
            adoption = await self.adoption(db, space.current_adoption_ref)
            return await self._workspace(db, account, space, adoption)

    async def current_goal(self, account: AccountView, space_id: UUID) -> SpaceGoalView:
        async with self.engine.connect() as db:
            space = await self.row(db, space_id)
            self.authorize(account, space)
            adoption = await self.adoption(db, space.current_adoption_ref)
            adopted = await self.adopted(db, adoption)
            result = await self.read_goal(db, space_id, adoption.target_basis_ref)
            domain = await db.scalar(
                text("SELECT domain_id FROM product.textbook WHERE textbook_id=:book"),
                {"book": space.textbook_id},
            )
        if not isinstance(domain, UUID):
            raise RuntimeError("Applied textbook has no domain reference")
        return SpaceGoalView(
            target_basis_ref=adopted.target_basis_ref,
            target_title=adopted.snapshot.target_title,
            domain_id=domain,
            pending=result is None,
            current=result,
        )

    async def domain_for(self, db: AsyncConnection, scope: UUID) -> UUID:
        identity = await db.scalar(
            text(
                "SELECT t.domain_id FROM product.learning_space s "
                "JOIN product.textbook t USING(textbook_id) WHERE s.space_id=:scope"
            ),
            {"scope": scope},
        )
        if not isinstance(identity, UUID):
            raise LookupError("The learning space has no adopted domain")
        return identity

    async def list_events(
        self, scope: UUID, event_types: tuple[str, ...], after: int, upper: int | None, limit: int
    ) -> dict[str, JsonValue]:
        async with self.engine.connect() as db:
            await self.row(db, scope)
        try:
            return await self.materials.reader.query_metadata(
                "learning_space",
                scope,
                filters=EventFilter(event_types=event_types),
                after_seq=after,
                upper_seq=upper,
                limit=limit,
            )
        except ValueError as error:
            raise RequestError(400, "invalid_request", str(error)) from error

    async def receipt(
        self, principal: UUID, _session: UUID, query: ReceiptQuery
    ) -> ReceiptView[SpaceOpenResult]:
        if principal != query.resource_id:
            return ReceiptView[SpaceOpenResult](receipt_state="not_found")
        async with self.engine.connect() as db:
            saved = await find_completed_request(
                db, principal, OPEN_SPACE, principal, query.request_id
            )
            if saved is None or saved.result_ref is None:
                return ReceiptView[SpaceOpenResult](receipt_state="not_found")
            name = await db.scalar(
                text(
                    "SELECT display_name FROM product.accounts "
                    "WHERE account_id=:id AND role='student'"
                ),
                {"id": principal},
            )
            if not isinstance(name, str):
                return ReceiptView[SpaceOpenResult](receipt_state="not_found")
            value = await self.entry_result(
                db,
                AccountView(account_id=principal, display_name=name, role="student", usage_gaps=[]),
                saved.request_ref,
                UUID(saved.result_ref.id),
            )
        return ReceiptView[SpaceOpenResult](
            receipt_state="completed",
            receipt_ref=saved.request_ref,
            result=value.result,
        )

    async def append(
        self,
        db: AsyncConnection,
        principal: UUID,
        request: UUID,
        drafts: Sequence[EventDraft],
        *,
        commit_id: UUID | None = None,
    ) -> None:
        scopes = frozenset((item.scope_kind, item.scope_id) for item in drafts)
        access = ProducerAccess("product", facts.ref("account", principal), scopes)
        expected = {
            (kind, identity): await lock_scope_sequence(db, kind, identity)
            for kind, identity in sorted(scopes)
        }
        for stored in await self.materials.events.append(
            db,
            access,
            drafts,
            expected_seq=expected,
            commit_id=commit_id or uuid4(),
            correlation_id=request,
        ):
            await facts.project(db, stored)

    async def row(
        self,
        db: AsyncConnection,
        space_id: UUID,
        *,
        lock: bool = False,
    ) -> facts.SpaceHead:
        sql = (
            "SELECT to_jsonb(s)-'source_event_id' FROM product.learning_space s "
            "WHERE space_id=:id" + (" FOR UPDATE" if lock else "")
        )
        found = await db.scalar(text(sql), {"id": space_id})
        if found is None:
            raise RequestError(404, "not_found", "找不到学习空间。")
        return facts.SpaceHead.model_validate_json(canonical_json(found))

    async def adoption(self, db: AsyncConnection, identity: UUID) -> facts.AdoptionRow:
        raw = await db.scalar(
            text(
                "SELECT to_jsonb(s)-'source_event_id' FROM product.space_adoption s WHERE "
                "adoption_id=:id"
            ),
            {"id": identity},
        )
        if raw is None:
            raise RuntimeError("Missing space adoption")
        return facts.AdoptionRow.model_validate_json(canonical_json(raw))

    async def adopted(self, db: AsyncConnection, adoption: facts.AdoptionRow) -> AdoptionView:
        snapshot = await db.scalar(
            text(
                "SELECT content_snapshot FROM product.course_application WHERE application_id=:id"
            ),
            {"id": adoption.application_ref},
        )
        if snapshot is None:
            raise RuntimeError("Missing adopted course")
        from deermind.product.public.courses import CourseSnapshot

        return AdoptionView(
            adoption_ref=facts.ref("space_adoption", adoption.adoption_id, adoption.adoption_seq),
            application_ref=facts.ref("course_application", adoption.application_ref),
            target_basis_ref=facts.ref("target_basis", adoption.target_basis_ref),
            snapshot=CourseSnapshot.model_validate_json(canonical_json(snapshot)),
        )

    async def protect_basis(self, db: AsyncConnection, scope: UUID) -> UUID:
        current = await self.row(db, scope, lock=True)
        return (await self.adoption(db, current.current_adoption_ref)).target_basis_ref

    async def fixed_adoption(
        self, db: AsyncConnection, scope: UUID, identity: UUID
    ) -> AdoptionView:
        adoption = await self.adoption(db, identity)
        if adoption.space_id != scope:
            raise RequestError(404, "not_found", "找不到此空间的采用记录。")
        return await self.adopted(db, adoption)

    async def chapter_content(
        self,
        account: AccountView,
        scope: UUID,
        chapter: UUID,
    ) -> list[dict[str, JsonValue]]:
        async with self.engine.connect() as db:
            space = await self.row(db, scope)
            self.authorize(account, space)
        return await self.fixed_chapter_content(scope, space.current_adoption_ref, chapter)

    async def fixed_chapter_content(
        self,
        scope: UUID,
        adoption: UUID,
        chapter: UUID | None,
        revision: int | None = None,
        *,
        source: Ref | None = None,
    ) -> list[dict[str, JsonValue]]:
        async with self.engine.connect() as db:
            adopted = await self.fixed_adoption(db, scope, adoption)
            chapter_view = next(
                (
                    row
                    for row in adopted.snapshot.chapters
                    if (
                        row.chapter_id == chapter and (revision is None or revision == row.revision)
                    )
                    or (source is not None and source in row.content_refs)
                ),
                None,
            )
            if chapter_view is None:
                raise RequestError(404, "not_found", "这个章节不在空间采用范围内。")
            parts: list[tuple[str, str, UUID, UUID, UUID]] = []
            selected = [source] if source is not None else chapter_view.content_refs
            for ref in selected:
                row = (
                    await db.execute(
                        text(
                            "SELECT kind,local_key,candidate_id,import_id,source_event_id FROM "
                            "product.material_candidate "
                            "WHERE candidate_id=:id AND candidate_revision=:revision"
                        ),
                        {"id": UUID(ref.id), "revision": ref.revision},
                    )
                ).one()
                parts.append(
                    (row.kind, row.local_key, row.import_id, row.source_event_id, row.candidate_id)
                )
        content: list[dict[str, JsonValue]] = []
        ordered = sorted(parts, key=lambda item: (CANDIDATE_ORDER[item[0]], item[1]))
        for _, _, import_id, event_id, candidate_id in ordered:
            found = await self.materials.reader.read_facts(
                "material_import",
                import_id,
                event_id,
                expected_event_type=PROPOSED,
                refs=[
                    EventPartRef(
                        event_id=event_id,
                        record_id=str(candidate_id),
                        path="/body",
                    )
                ],
            )
            items = found["items"]
            assert isinstance(items, list) and isinstance(items[0], dict)
            body = items[0]["content"]
            assert isinstance(body, dict)
            reference = next(item for item in selected if item.id == str(candidate_id))
            content.append({**body, "source_ref": reference.model_dump(mode="json")})
        if len(canonical_json(content).encode()) > 4 * 1024**2:
            raise RequestError(413, "payload_too_large", "章节正文超过读取限额。")
        return content

    async def read_quoted_content(
        self, scope: UUID, adoption: UUID, reference: Ref
    ) -> list[dict[str, JsonValue]]:
        if reference.type == "material_candidate":
            return await self.fixed_chapter_content(scope, adoption, None, source=reference)
        return await self.fixed_chapter_content(
            scope, adoption, UUID(reference.id), reference.revision
        )

    def build_adoption(
        self,
        space: facts.SpaceHead,
        course: facts.CourseRow,
        previous: facts.AdoptionRow | None,
        now: datetime,
        request_id: str,
    ) -> tuple[facts.AdoptionRow, list[EventDraft]]:
        adoption_id, event_id = uuid4(), uuid4()
        sequence = previous.adoption_seq + 1 if previous else 1
        adopted = facts.AdoptionRow(
            adoption_id=adoption_id,
            space_id=space.space_id,
            adoption_seq=sequence,
            application_ref=course.application_id,
            target_basis_ref=course.target_basis_ref,
            previous_adoption_id=previous.adoption_id if previous else None,
            reason="course_application" if previous else "student_selection",
            event_ref=event_id,
            created_at=now,
        )
        space = space.model_copy(update={"current_adoption_ref": adoption_id})
        adoption_ref = facts.ref("space_adoption", adopted.adoption_id, sequence)
        basis = facts.ref("target_basis", adopted.target_basis_ref)
        application_ref = facts.ref("course_application", course.application_id)
        scope = ("learning_space", space.space_id)
        owner = facts.ref("learning_space", space.space_id)
        records = [
            facts.record(facts.SPACE, space.space_id, space),
            facts.record(facts.SPACE_ADOPTION, adoption_id, adopted),
        ]
        old_basis = facts.ref("target_basis", previous.target_basis_ref) if previous else None
        if previous is None:
            change = facts.event(
                facts.CREATED,
                scope,
                owner,
                facts.LearningSpaceCreated(
                    student_id=space.student_id,
                    textbook_id=space.textbook_id,
                    target_id=space.target_id,
                    adoption_ref=adoption_ref,
                    records=records,
                ),
                identity=event_id,
                request_id=request_id,
            )
        else:
            assert old_basis is not None
            change = facts.event(
                facts.ADOPTION,
                scope,
                owner,
                facts.LearningSpaceAdoptionChanged(
                    previous_adoption_ref=facts.ref(
                        "space_adoption", previous.adoption_id, previous.adoption_seq
                    ),
                    adoption_ref=adoption_ref,
                    previous_target_basis_ref=old_basis,
                    target_basis_ref=basis,
                    cause_ref=application_ref,
                    records=records,
                ),
                identity=event_id,
                request_id=request_id,
            )
        drafts = [change]
        if old_basis != basis:
            drafts.append(
                facts.event(
                    facts.TARGET_APPLIED,
                    scope,
                    owner,
                    facts.LearningTargetApplied(
                        adoption_ref=adoption_ref,
                        application_ref=application_ref,
                        target_basis_ref=basis,
                        previous_target_basis_ref=old_basis,
                        applied_at=now,
                        cause_ref=facts.ref("event", event_id),
                        records=[],
                    ),
                    request_id=request_id,
                )
            )
        return adopted, drafts

    def authorize(self, caller: AccountView, space: facts.SpaceHead) -> None:
        if caller.role == "student" and caller.account_id != space.student_id:
            raise RequestError(404, "not_found", "找不到学习空间。")

    async def entry_result(
        self, db: AsyncConnection, account: AccountView, request: UUID, event_id: UUID
    ) -> SpaceReceipt:
        scope = await db.scalar(
            text(
                "SELECT e.scope_id FROM runtime.events e JOIN product.learning_space s "
                "ON s.space_id=e.scope_id WHERE e.event_id=:id AND e.event_type=:kind "
                "AND e.correlation_id=:request AND s.student_id=:student"
            ),
            {
                "id": event_id,
                "kind": facts.ENTERED,
                "request": request,
                "student": account.account_id,
            },
        )
        if scope is None:
            raise RequestError(404, "not_found", "找不到空间进入记录。")
        space = await self.row(db, scope)
        data = await self.materials.reader.read_facts(
            "learning_space",
            scope,
            event_id,
            expected_event_type=facts.ENTERED,
            correlation_id=request,
            refs=[EventPartRef(event_id=event_id, record_id=None, path="")],
        )
        parts = data["items"]
        assert isinstance(parts, list) and isinstance(parts[0], dict)
        body = parts[0]["content"]
        assert isinstance(body, dict)
        entry = facts.LearningSpaceEntered.model_validate_json(
            canonical_json({**body, "records": []})
        )
        adoption = await self.adoption(db, UUID(entry.adoption_ref.id))
        return await self._opened(db, account, request, space, adoption, event_id, entry.created)

    async def _opened(
        self,
        db: AsyncConnection,
        account: AccountView,
        request: UUID,
        space: facts.SpaceHead,
        adoption: facts.AdoptionRow,
        identity: UUID,
        created: bool,
    ) -> SpaceReceipt:
        workspace = await self._workspace(db, account, space, adoption)
        return SpaceReceipt(
            request_ref=request,
            result=SpaceOpenResult(
                space=workspace.space,
                created=created,
                adoption=workspace.adoption,
                entry_event_ref=identity,
            ),
        )

    async def _workspace(
        self,
        db: AsyncConnection,
        account: AccountView,
        space: facts.SpaceHead,
        adoption: facts.AdoptionRow,
    ) -> SpaceWorkspace:
        view = await self.adopted(db, adoption)
        return SpaceWorkspace(
            space=SpaceRow(
                space_id=space.space_id,
                student_id=space.student_id,
                student_name=account.display_name,
                textbook_id=space.textbook_id,
                target_id=space.target_id,
                created_at=space.created_at,
                textbook_title=view.snapshot.textbook_title,
                target_title=view.snapshot.target_title,
            ),
            adoption=view,
        )

    async def open(self, account: AccountView, command: SpaceCommand) -> SpaceReceipt:
        request = uuid4()
        async with self.engine.begin() as db:
            receipt = await claim_request(
                db,
                principal_id=str(account.account_id),
                action=OPEN_SPACE,
                scope_id=str(account.account_id),
                request_id=command.request_id,
                normalized_input=command.model_dump(mode="json"),
                reserved_ref=request,
            )
            if receipt.result_ref is not None:
                return await self.entry_result(
                    db, account, receipt.request_ref, UUID(receipt.result_ref.id)
                )
            now = datetime.now(UTC)
            created = False
            drafts: list[EventDraft] = []
            if isinstance(command, CreateSpace):
                await self.checks.book(db, command.textbook_id, lock=True)
                course = await self.checks.current(db, command.textbook_id, command.target_id)
                if course is None:
                    raise RequestError(409, "not_ready", "该教材与目标尚未应用。")
                if command.expected_application_ref != facts.ref(
                    "course_application", course.application_id
                ):
                    raise RequestError(409, "application_changed", "课程已更新，请刷新后选择。")
                identity = await db.scalar(
                    text(
                        "SELECT space_id FROM product.learning_space "
                        "WHERE student_id=:student AND textbook_id=:book AND target_id=:target"
                    ),
                    {
                        "student": account.account_id,
                        "book": command.textbook_id,
                        "target": command.target_id,
                    },
                )
                if identity is None:
                    created = True
                    space = facts.SpaceHead(
                        space_id=uuid4(),
                        student_id=account.account_id,
                        textbook_id=command.textbook_id,
                        target_id=command.target_id,
                        current_adoption_ref=uuid4(),
                        created_at=now,
                    )
                    adoption, drafts = self.build_adoption(
                        space, course, None, now, command.request_id
                    )
                else:
                    space = await self.row(db, identity, lock=True)
                    adoption = await self.adoption(db, space.current_adoption_ref)
            else:
                space = await self.row(db, command.space_id, lock=True)
                self.authorize(account, space)
                adoption = await self.adoption(db, space.current_adoption_ref)
            entry = facts.event(
                facts.ENTERED,
                ("learning_space", space.space_id),
                facts.ref("learning_space", space.space_id),
                facts.LearningSpaceEntered(
                    adoption_ref=facts.ref(
                        "space_adoption", adoption.adoption_id, adoption.adoption_seq
                    ),
                    application_ref=facts.ref("course_application", adoption.application_ref),
                    target_basis_ref=facts.ref("target_basis", adoption.target_basis_ref),
                    request_ref=request,
                    created=created,
                    records=[],
                ),
                request_id=command.request_id,
            )
            await self.append(db, account.account_id, request, [*drafts, entry])
            await complete_request(db, receipt, facts.ref("space_entry", entry.event_id))
            return await self._opened(
                db, account, request, space, adoption, entry.event_id, created
            )

    async def options(
        self,
        account: AccountView,
        domain: UUID | None,
        cursor: str | None,
        limit: int,
    ) -> CourseOptions:
        token = sha256(f"{account.account_id}:course:{domain}".encode()).hexdigest()
        after = cursor_position(cursor, token)
        async with self.engine.connect() as db:
            rows = (
                await db.execute(
                    text(
                        "SELECT a.application_id,a.textbook_id,a.content_snapshot FROM "
                        "product.application_head h "
                        "JOIN product.course_application a ON "
                        "a.application_id=h.current_application_ref "
                        "JOIN product.textbook t ON t.textbook_id=h.textbook_id "
                        "WHERE (CAST(:domain AS uuid) IS NULL OR t.domain_id=:domain) "
                        "AND (CAST(:after AS uuid) IS NULL OR a.application_id>:after) "
                        "ORDER BY a.application_id LIMIT :limit"
                    ),
                    {"domain": domain, "after": after, "limit": limit + 1},
                )
            ).all()
        return CourseOptions(
            items=[
                CourseOption(
                    textbook_id=row.textbook_id,
                    textbook_title=row.content_snapshot["textbook_title"],
                    target_ref=row.content_snapshot["target_ref"],
                    target_title=row.content_snapshot["target_title"],
                    application_ref=facts.ref("course_application", row.application_id),
                )
                for row in rows[:limit]
            ],
            next_cursor=f"{token}.{rows[limit - 1].application_id}" if len(rows) > limit else None,
        )

    async def list_spaces(
        self,
        account: AccountView,
        student: UUID | None,
        textbook: UUID | None,
        target: UUID | None,
        name: str,
        cursor: str | None,
        limit: int,
    ) -> SpaceList:
        if account.role == "student":
            if student not in (None, account.account_id):
                raise RequestError(404, "not_found", "找不到学习空间。")
            student = account.account_id
        token = sha256(
            f"{account.account_id}:{student}:{textbook}:{target}:{name}".encode()
        ).hexdigest()
        after = cursor_position(cursor, token)
        async with self.engine.connect() as db:
            rows = (
                (
                    await db.execute(
                        text(
                            "SELECT s.space_id,s.student_id,p.display_name AS "
                            "student_name,s.created_at,"
                            "s.textbook_id,s.target_id,c.content_snapshot->>'target_title' AS "
                            "target_title,"
                            "c.content_snapshot->>'textbook_title' AS textbook_title "
                            "FROM product.learning_space s JOIN product.accounts p ON "
                            "p.account_id=s.student_id "
                            "JOIN product.space_adoption a ON a.adoption_id=s.current_adoption_ref "
                            "JOIN product.course_application c ON "
                            "c.application_id=a.application_ref "
                            "WHERE (CAST(:student AS uuid) IS NULL OR s.student_id=:student) "
                            "AND (CAST(:book AS uuid) IS NULL OR s.textbook_id=:book) "
                            "AND (CAST(:target AS uuid) IS NULL OR s.target_id=:target) "
                            "AND strpos(lower(p.display_name),lower(:name))>0 "
                            "AND (CAST(:after AS uuid) IS NULL OR s.space_id>:after) ORDER BY "
                            "s.space_id LIMIT :limit"
                        ),
                        {
                            "student": student,
                            "book": textbook,
                            "target": target,
                            "name": name,
                            "after": after,
                            "limit": limit + 1,
                        },
                    )
                )
                .mappings()
                .all()
            )
        return SpaceList(
            items=[SpaceRow.model_validate(dict(row)) for row in rows[:limit]],
            next_cursor=f"{token}.{rows[limit - 1]['space_id']}" if len(rows) > limit else None,
        )
