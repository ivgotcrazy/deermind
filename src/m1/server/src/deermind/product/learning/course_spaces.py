"""Freeze the student's adopted course and append entry/target events."""

from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal
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
from deermind.spaces.domain.public import SolutionRef
from deermind.spaces.evaluation.public import GoalEvaluation
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

type ReadGoal = Callable[[AsyncConnection, UUID, UUID], Awaitable[GoalEvaluation | None]]
type ReadProgress = Callable[
    [AsyncConnection, UUID], Awaitable[Literal["pending", "failed"] | None]
]
type ReadMethodName = Callable[[AsyncConnection, UUID, SolutionRef], Awaitable[str | None]]
CANDIDATE_ORDER = {"kc": 0, "task_instance": 1, "reference": 2}


class CourseSpaces:
    def __init__(
        self,
        checks: CourseChecks,
        read_goal: ReadGoal,
        read_progress: ReadProgress,
        read_method_name: ReadMethodName,
    ) -> None:
        self.checks = checks
        self.engine = checks.engine
        self.materials = checks.materials
        self.read_goal = read_goal
        self.read_progress = read_progress
        self.read_method_name = read_method_name

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
            processing = await self.read_progress(db, space_id)
            domain = await db.scalar(
                text("SELECT domain_id FROM product.textbook WHERE textbook_id=:book"),
                {"book": space.textbook_id},
            )
        if not isinstance(domain, UUID):
            # 已采用教材缺少领域引用，数据不一致。
            raise RuntimeError("Applied textbook has no domain reference")
        return SpaceGoalView(
            target_basis_ref=adopted.target_basis_ref,
            target_title=adopted.snapshot.target_title,
            domain_id=domain,
            pending=result is None,
            current=result,
            evaluation_processing=processing,
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
            # 空间尚未采用教材，没有可追溯的领域。
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
            # 事件序号/游标参数非法，转为请求错误。
            raise RequestError(400, "invalid_request", str(error)) from error

    async def receipt(
        self, principal: UUID, _session: UUID, query: ReceiptQuery
    ) -> ReceiptView[SpaceOpenResult]:
        if principal != query.resource_id:
            # 回执按学生自身作用域定位，他人空间不对外可见。
            return ReceiptView[SpaceOpenResult](receipt_state="not_found")
        async with self.engine.connect() as db:
            saved = await find_completed_request(
                db, principal, OPEN_SPACE, principal, query.request_id
            )
            if saved is None or saved.result_ref is None:
                # 无已完成回执，或回执尚未落结果。
                return ReceiptView[SpaceOpenResult](receipt_state="not_found")
            name = await db.scalar(
                text(
                    "SELECT display_name FROM product.accounts "
                    "WHERE account_id=:id AND role='student'"
                ),
                {"id": principal},
            )
            if not isinstance(name, str):
                # 回执主体已不是学生账号，回执结果不再对外返回。
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
            "SELECT to_jsonb(s)-'source_event_id'-'application_ref'-'last_entered_at' "
            "FROM product.learning_space s "
            "WHERE space_id=:id" + (" FOR UPDATE" if lock else "")
        )
        found = await db.scalar(text(sql), {"id": space_id})
        if found is None:
            # 空间记录不存在。
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
            # 采用记录缺失，属数据不一致。
            raise RuntimeError("Missing space adoption")
        return facts.AdoptionRow.model_validate_json(canonical_json(raw))

    async def adopted(self, db: AsyncConnection, adoption: facts.AdoptionRow) -> AdoptionView:
        course = (
            await db.execute(
                text(
                    "SELECT content_snapshot,revision FROM product.course_application "
                    "WHERE application_id=:id"
                ),
                {"id": adoption.application_ref},
            )
        ).one_or_none()
        if course is None:
            # 采用记录指向的课程版本已不存在。
            raise RuntimeError("Missing adopted course")
        from deermind.product.public.courses import CourseSnapshot

        return AdoptionView(
            adoption_ref=facts.ref("space_adoption", adoption.adoption_id, adoption.adoption_seq),
            application_ref=facts.ref("course_application", adoption.application_ref),
            application_version=course.revision,
            target_basis_ref=facts.ref("target_basis", adoption.target_basis_ref),
            snapshot=CourseSnapshot.model_validate_json(canonical_json(course.content_snapshot)),
        )

    async def protect_basis(self, db: AsyncConnection, scope: UUID) -> UUID:
        current = await self.row(db, scope, lock=True)
        return (await self.adoption(db, current.current_adoption_ref)).target_basis_ref

    async def fixed_adoption(
        self, db: AsyncConnection, scope: UUID, identity: UUID
    ) -> AdoptionView:
        adoption = await self.adoption(db, identity)
        if adoption.space_id != scope:
            # 采用记录属于其他空间，不跨空间暴露。
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
                # 按章节号/版本或内容引用都未在本空间快照中命中。
                raise RequestError(404, "not_found", "这个章节不在空间采用范围内。")
            if adopted.snapshot.extraction_id:
                from deermind.product.materials.editions import read_edition

                book = (await self.row(db, scope)).textbook_id
                extraction = await read_edition(db, book, adopted.snapshot.extraction_id)
                assert extraction.tree_id is not None
                tree = await read_edition(db, book, extraction.tree_id)
                nodes = {str(n.node_id): n for n in tree.nodes}
                selected_refs = [source] if source else chapter_view.content_refs
                return [
                    {
                        "source_ref": r.model_dump(mode="json"),
                        "content": nodes[r.id].content,
                        "kind": nodes[r.id].node_kind,
                        "pages": [str(p) for p in nodes[r.id].covered_page_ids],
                    }
                    for r in selected_refs
                    if r in chapter_view.content_refs
                ]
            parts: list[tuple[str, str, UUID, UUID, UUID]] = []
            selected = [source] if source is not None else chapter_view.content_refs
            # 逐份候选内容取出类型、本地编号与溯源事件。
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
        # 按候选类型优先级（KC→题目→参考）与本地编号排序，保证正文呈现顺序稳定。
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
            # 章节合并正文超出单次读取的 4MB 限额。
            raise RequestError(413, "payload_too_large", "章节正文超过读取限额。")
        return content

    async def read_quoted_content(
        self, scope: UUID, adoption: UUID, reference: Ref
    ) -> list[dict[str, JsonValue]]:
        if reference.owner == "product" and reference.type == "material_content_node":
            async with self.engine.connect() as db:
                adopted = await self.fixed_adoption(db, scope, adoption)
                row = (
                    await db.execute(
                        text("""
                    SELECT n.node_kind,n.content,n.covered_page_ids
                    FROM product.material_edition e
                    JOIN product.material_edition t ON t.edition_id=e.tree_id
                    JOIN product.material_content_node n ON n.material_version_id=t.edition_id
                    WHERE e.edition_id=:edition AND e.status='published' AND t.status='published'
                    AND t.number=:revision AND n.node_id=CAST(:node AS uuid)
                """),
                        {
                            "edition": adopted.snapshot.extraction_id,
                            "revision": reference.revision,
                            "node": reference.id,
                        },
                    )
                ).one_or_none()
            if row is None:
                raise RequestError(404, "not_found", "该原文不属于学习空间固定的教材版本。")
            return [
                {
                    "source_ref": reference.model_dump(mode="json"),
                    "content": row.content,
                    "kind": row.node_kind,
                    "pages": [str(p) for p in row.covered_page_ids],
                }
            ]
        if reference.type == "material_candidate":
            # 直接引用候选内容：按来源候选定位，不绑定章节。
            return await self.fixed_chapter_content(scope, adoption, None, source=reference)
        return await self.fixed_chapter_content(
            scope, adoption, UUID(reference.id), reference.revision
        )

    def _initial_adoption(
        self,
        space: facts.SpaceHead,
        course: facts.CourseRow,
        now: datetime,
        request_id: str,
    ) -> tuple[facts.AdoptionRow, list[EventDraft]]:
        adoption_id, event_id = space.current_adoption_ref, uuid4()
        adopted = facts.AdoptionRow(
            adoption_id=adoption_id,
            space_id=space.space_id,
            adoption_seq=1,
            application_ref=course.application_id,
            target_basis_ref=course.target_basis_ref,
            previous_adoption_id=None,
            reason="student_selection",
            event_ref=event_id,
            created_at=now,
        )
        adoption_ref = facts.ref("space_adoption", adopted.adoption_id, 1)
        basis = facts.ref("target_basis", adopted.target_basis_ref)
        application_ref = facts.ref("course_application", course.application_id)
        scope = ("learning_space", space.space_id)
        owner = facts.ref("learning_space", space.space_id)
        records = [
            facts.record(facts.SPACE, space.space_id, space),
            facts.record(facts.SPACE_ADOPTION, adoption_id, adopted),
        ]
        return adopted, [
            facts.event(
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
            ),
            facts.event(
                facts.TARGET_APPLIED,
                scope,
                owner,
                facts.LearningTargetApplied(
                    adoption_ref=adoption_ref,
                    application_ref=application_ref,
                    target_basis_ref=basis,
                    previous_target_basis_ref=None,
                    applied_at=now,
                    cause_ref=facts.ref("event", event_id),
                    records=[],
                ),
                request_id=request_id,
            ),
        ]

    def authorize(self, caller: AccountView, space: facts.SpaceHead) -> None:
        if caller.role == "student" and caller.account_id != space.student_id:
            # 学生只能访问自己的空间；他人空间按不存在处理，避免泄露存在性。
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
            # 未在当前学生名下命中该进入事件。
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
                study_methods=workspace.study_methods,
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
        methods = {
            (method.method_ref.object_id, method.method_ref.version): method.method_ref
            for item in view.snapshot.items
            for method in item.methods
        }
        names: dict[str, None] = {}
        if methods:
            # 快照中存在方法时，再读取领域名汇总学习方法清单。
            domain = await self.domain_for(db, space.space_id)
            for method in methods.values():
                name = await self.read_method_name(db, domain, method)
                if name:
                    # 方法名去重后归集。
                    names[name] = None
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
                target_revision=view.snapshot.target_ref.revision,
                application_ref=view.application_ref,
                application_version=view.application_version,
            ),
            adoption=view,
            study_methods=list(names),
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
                # 进入请求幂等重放，回原进入事件结果。
                return await self.entry_result(
                    db, account, receipt.request_ref, UUID(receipt.result_ref.id)
                )
            now = datetime.now(UTC)
            created = False
            drafts: list[EventDraft] = []
            if isinstance(command, CreateSpace):
                # 新建空间路径：加锁读取教材，核对目标上是否已有已发布课程。
                await self.checks.book(db, command.textbook_id, lock=True)
                course = await self.checks.current(db, command.textbook_id, command.target_id)
                if course is None:
                    # 教材与目标组合尚未应用课程，不能建空间。
                    raise RequestError(409, "not_ready", "该教材与目标尚未应用。")
                if command.expected_application_ref != facts.ref(
                    "course_application", course.application_id
                ):
                    # 当前课程版本与命令选择时不一致。
                    raise RequestError(409, "application_changed", "课程已更新，请刷新后选择。")
                identity = await db.scalar(
                    text(
                        "SELECT space_id FROM product.learning_space "
                        "WHERE student_id=:student AND application_ref=:application"
                    ),
                    {
                        "student": account.account_id,
                        "application": course.application_id,
                    },
                )
                if identity is None:
                    # 该学生尚无对应课程的空间，新建空间并落初始采用。
                    created = True
                    space = facts.SpaceHead(
                        space_id=uuid4(),
                        student_id=account.account_id,
                        textbook_id=command.textbook_id,
                        target_id=command.target_id,
                        current_adoption_ref=uuid4(),
                        created_at=now,
                    )
                    adoption, drafts = self._initial_adoption(
                        space, course, now, command.request_id
                    )
                else:
                    # 已有同课程空间，直接复用其当前采用。
                    space = await self.row(db, identity, lock=True)
                    adoption = await self.adoption(db, space.current_adoption_ref)
            else:
                # 进入既有空间路径：加锁取空间并做归属复核。
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
                        "SELECT a.application_id,a.textbook_id,a.content_snapshot,a.revision FROM "
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
                    application_version=row.revision,
                )
                for row in rows[:limit]
            ],
            # 多取一条判断是否还有下一页；超出限额才生成续页游标。
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
                # 学生不能按他人账号过滤空间。
                raise RequestError(404, "not_found", "找不到学习空间。")
            # 强制按本人账号过滤。
            student = account.account_id
        token = sha256(
            f"{account.account_id}:{student}:{textbook}:{target}:{name}".encode()
        ).hexdigest()
        after = cursor_position(cursor, token)
        async with self.engine.connect() as db:
            recent = None
            if account.role == "student":
                # 学生列表额外回填最近进入的空间。
                recent = await db.scalar(
                    text("""
                        SELECT space_id FROM product.learning_space
                        WHERE student_id=:student AND last_entered_at IS NOT NULL
                        ORDER BY last_entered_at DESC,space_id LIMIT 1
                    """),
                    {"student": account.account_id},
                )
            rows = (
                (
                    await db.execute(
                        text(
                            "SELECT s.space_id,s.student_id,p.display_name AS "
                            "student_name,s.created_at,"
                            "s.textbook_id,s.target_id,c.revision AS application_version,"
                            "jsonb_build_object('owner','product','type','course_application',"
                            "'id',c.application_id) AS application_ref,"
                            "(c.content_snapshot->'target_ref'->>'revision')::integer "
                            "AS target_revision,c.content_snapshot->>'target_title' AS "
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
            # 多取一条判断是否还有下一页；超出限额才生成续页游标。
            next_cursor=f"{token}.{rows[limit - 1]['space_id']}" if len(rows) > limit else None,
            recent_space_id=recent,
        )
