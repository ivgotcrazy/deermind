"""Manage whole-book drafts and immutable published editions."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from deermind.abstractions.events import EventDraft, EventPayload, ProducerAccess, Ref
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.public.errors import RequestError
from deermind.product.materials import edition_facts
from deermind.product.materials.content_tree import validate_tree
from deermind.product.materials.facts import record
from deermind.product.materials.receiving import MaterialReceiving
from deermind.product.persistence.receipts import claim_request, complete_request
from deermind.product.public.authentication import SessionView
from deermind.product.public.material_editions import (
    BookPage,
    ChapterTask,
    ContentNode,
    Edition,
    EditionCommand,
    EditionInfo,
    EditionUsage,
    MapTask,
    StudentBook,
)
from deermind.spaces.domain.public import (
    KnowledgeRef,
    KnowledgeView,
    SolutionRef,
    SolutionView,
    TaskView,
)
from pydantic_core import to_json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_COLUMNS = "edition_id,textbook_id,kind,number,tree_id,status,revision,created_at"


async def pages_of(db: AsyncConnection, book: UUID) -> list[BookPage]:
    rows = await db.execute(
        text("""
        SELECT s.* FROM product.material_source s JOIN product.textbook t USING(import_id)
        WHERE t.textbook_id=:book ORDER BY source_order
    """),
        {"book": book},
    )
    return [
        BookPage(
            page_id=UUID(page["page_id"]),
            source_id=r.source_id,
            file_id=r.file_id,
            name=r.original_name,
            index=page["file_page_index"],
            printed=page["printed_page_label"],
        )
        for r in rows
        for page in r.pages
    ]


async def read_edition(
    db: AsyncConnection, book: UUID, edition: UUID, page: UUID | None = None
) -> Edition:
    row = (
        (
            await db.execute(
                text(
                    "SELECT * FROM product.material_edition "
                    "WHERE textbook_id=:book AND edition_id=:id AND status<>'discarded'"
                ),
                {"book": book, "id": edition},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise RequestError(404, "not_found", "找不到该教材版本。")
    predicate = " AND covered_page_ids @> ARRAY[CAST(:page AS uuid)]" if page else ""
    nodes = (
        await db.execute(
            text(
                "SELECT node_id,parent_id,node_kind,sibling_order,content,covered_page_ids "
                "FROM product.material_content_node WHERE material_version_id=:id"
                + predicate
                + " ORDER BY parent_id NULLS FIRST,sibling_order"
            ),
            {"id": edition, "page": page},
        )
    ).mappings()
    return Edition.model_validate_json(
        to_json(
            {
                **{key: row[key] for key in _COLUMNS.split(",")},
                "pages": row["pages"],
                "entries": row["entries"],
                "nodes": [dict(n) for n in nodes],
                "base_edition_id": row["pending"].get("base_edition_id"),
                "pending": row["pending"]["correction"],
                "issues": row["pending"]["issues"],
                "related_tasks": row["pending"]["related"],
            },
        )
    )


class MaterialEditions:
    def __init__(self, materials: MaterialReceiving) -> None:
        self.materials = materials
        self.engine = materials.engine

    async def pages(self, book: UUID) -> list[BookPage]:
        async with self.engine.connect() as db:
            return await pages_of(db, book)

    async def for_target(self, book: UUID, target: UUID, revision: int) -> StudentBook | None:

        async with self.engine.connect() as db:
            identity = await db.scalar(
                text(
                    "SELECT v.extraction_id FROM product.learning_target_version v "
                    "JOIN product.learning_target h USING(target_id) WHERE h.textbook_id=:book "
                    "AND v.target_id=:id AND v.revision=:revision"
                ),
                {"book": book, "id": target, "revision": revision},
            )
            if identity is None:
                return None
            extraction = await read_edition(db, book, identity)
            if extraction.status != "published" or not extraction.tree_id:
                raise RequestError(409, "invalid_reference", "课程未绑定已发布的教学提炼。")
            tree = await read_edition(db, book, extraction.tree_id)
            return StudentBook(
                tree=tree, extraction=extraction, related_tasks=extraction.related_tasks
            )

    async def listing(self, book: UUID) -> list[EditionInfo]:
        async with self.engine.connect() as db:
            rows = await db.execute(
                text(
                    f"SELECT {_COLUMNS} FROM product.material_edition "
                    "WHERE textbook_id=:book AND status<>'discarded' ORDER BY created_at DESC"
                ),
                {"book": book},
            )
            return [EditionInfo.model_validate(dict(row)) for row in rows.mappings()]

    async def detail(self, book: UUID, edition: UUID, page: UUID | None = None) -> Edition:
        async with self.engine.connect() as db:
            return await read_edition(db, book, edition, page)

    async def usage(self, book: UUID, edition: UUID) -> list[EditionUsage]:
        async with self.engine.connect() as db:
            rows = await db.execute(
                text("""
                SELECT v.target_id,v.revision,v.title FROM product.learning_target_version v
                JOIN product.learning_target h USING(target_id)
                WHERE h.textbook_id=:book AND v.extraction_id=:id ORDER BY v.title,v.revision
            """),
                {"book": book, "id": edition},
            )
            return [
                EditionUsage(
                    title=r.title,
                    target_ref=Ref(
                        owner="product",
                        type="learning_target",
                        id=str(r.target_id),
                        revision=r.revision,
                    ),
                )
                for r in rows
            ]

    async def catalog(self, session: SessionView, domain: UUID) -> list[MapTask]:
        service = self.materials.domain
        cursor = None
        tasks: list[MapTask] = []
        while True:
            batch = await service.list_members(session, domain, "", cursor, 100, ["task"])
            for member in batch.items:
                if member.is_deleted:
                    continue
                identity = member.object_ref
                task = (
                    await service.read_object(session, domain, identity.object_id, identity.version)
                ).object
                if not isinstance(task, TaskView):
                    continue
                names: list[str] = []
                methods: list[SolutionRef] = []
                method_knowledge: list[list[KnowledgeRef]] = []
                knowledge: dict[KnowledgeRef, str] = {}
                for ref in task.content.method_refs:
                    method = (
                        await service.read_object(session, domain, ref.object_id, ref.version)
                    ).object
                    if not isinstance(method, SolutionView) or method.is_identity_deleted:
                        continue
                    methods.append(ref)
                    method_knowledge.append(method.content.kc_refs)
                    names.append(method.content.name)
                    for kc in method.content.kc_refs:
                        if kc not in knowledge:
                            item = (
                                await service.read_object(session, domain, kc.object_id, kc.version)
                            ).object
                            if isinstance(item, KnowledgeView):
                                knowledge[kc] = item.content.name
                tasks.append(
                    MapTask(
                        chapter_id=domain,
                        task_ref=task.object_ref,
                        name=task.content.name,
                        method_refs=methods,
                        method_names=names,
                        method_knowledge=method_knowledge,
                        knowledge=list(knowledge),
                        knowledge_names=list(knowledge.values()),
                        prerequisites=task.content.prerequisites,
                    )
                )
            cursor = batch.next_cursor
            if cursor is None:
                return tasks

    async def persist(self, db: AsyncConnection, actor: Ref, value: Edition, request: UUID) -> None:
        scope = ("textbook", value.textbook_id)
        event = uuid4()
        owner = Ref(
            owner="product",
            type="material_edition",
            id=str(value.edition_id),
            revision=value.revision,
        )
        payload = EventPayload(records=[record(edition_facts.RECORD, value.edition_id, value)])
        draft = EventDraft(
            event,
            edition_facts.EVENT,
            1,
            *scope,
            owner,
            payload.model_dump(mode="json"),
            str(request),
        )
        access = ProducerAccess("product", actor, frozenset({scope}))
        prepared = await self.materials.attachments.prepare(self.materials.events, access, (draft,))
        seq = await lock_scope_sequence(db, *scope)
        (stored,) = await self.materials.events.append(
            db,
            access,
            prepared,
            commit_id=uuid4(),
            correlation_id=request,
            expected_seq={scope: seq},
        )
        await edition_facts.project(db, stored)

    async def command(
        self, session: SessionView, book: UUID, identity: UUID, cmd: EditionCommand
    ) -> EditionInfo:
        principal = self.materials.administrator(session)
        actor = Ref(owner="product", type="account", id=str(principal))
        async with self.engine.begin() as db:
            receipt = await claim_request(
                db,
                principal_id=str(principal),
                action="product.edit_material_edition",
                scope_id=str(book),
                request_id=cmd.request_id,
                normalized_input={"edition": str(identity), **cmd.model_dump(mode="json")},
            )
            if receipt.result_ref:
                row = (
                    (
                        await db.execute(
                            text(
                                f"SELECT {_COLUMNS} FROM product.material_edition "
                                "WHERE edition_id=:id"
                            ),
                            {"id": UUID(receipt.result_ref.id)},
                        )
                    )
                    .mappings()
                    .one()
                )
                status = {"publish": "published", "discard": "discarded"}.get(cmd.action, "draft")
                return EditionInfo.model_validate(
                    {**dict(row), "status": status, "revision": receipt.result_ref.revision}
                )
            imported = (
                await db.execute(
                    text("SELECT import_id,domain_id FROM product.textbook WHERE textbook_id=:id"),
                    {"id": book},
                )
            ).one_or_none()
            if not imported:
                raise RequestError(404, "not_found", "教材不存在。")
            await self.materials.read_import(db, imported.import_id, lock=True)
            value = await read_edition(db, book, identity)
            if value.revision != cmd.revision:
                raise RequestError(409, "revision_conflict", "版本已变化，请刷新后重试。")
            if cmd.action == "copy" and value.status == "published":
                value = await new_draft(db, value, uuid4(), base=value.edition_id)
            elif value.status != "draft" or cmd.action == "copy":
                raise RequestError(409, "revision_conflict", "已发布版本只读，请从发布版建草稿。")
            else:
                value = value.model_copy(update={"revision": value.revision + 1})
                if cmd.action == "publish":
                    if (
                        value.pending is not None
                        or value.issues
                        or (value.kind == "extraction" and not value.entries)
                    ):
                        raise RequestError(409, "incomplete", "请先处理待核对内容并补全教学任务。")
                    if value.kind == "tree":
                        validate_tree(value.nodes, value.pages)
                    else:
                        for entry in value.entries:
                            for definition in [entry.task_ref, *entry.method_refs]:
                                item = await self.materials.domain.read_object(
                                    session,
                                    imported.domain_id,
                                    definition.object_id,
                                    definition.version,
                                )
                                if item.object.is_identity_deleted:
                                    raise RequestError(
                                        409,
                                        "invalid_reference",
                                        "任务或方法已退役，请调整本节后发布。",
                                    )
                    value = value.model_copy(update={"status": "published"})
                elif cmd.action == "discard":
                    value = value.model_copy(update={"status": "discarded"})
                elif cmd.action in {"apply_correction", "reject_correction"}:
                    if value.pending is None:
                        raise RequestError(409, "revision_conflict", "当前草稿没有待处理的修正。")
                    nodes = value.pending if cmd.action == "apply_correction" else value.nodes
                    value = value.model_copy(update={"nodes": nodes, "pending": None})
                elif cmd.action == "edit_tasks":
                    if value.tree_id is None or cmd.chapter_id is None:
                        raise RequestError(400, "invalid_reference", "请选择提炼草稿中的章节。")
                    tree = await read_edition(db, book, value.tree_id)
                    if not any(
                        n.node_id == cmd.chapter_id
                        and n.node_kind in {"chapter", "section", "unit"}
                        for n in tree.nodes
                    ) or any(t.chapter_id != cmd.chapter_id for t in cmd.tasks):
                        raise RequestError(400, "invalid_reference", "任务章节不属于本版内容树。")
                    catalog = await self.catalog(session, imported.domain_id)
                    changed = select_tasks(cmd.tasks, catalog, tree.nodes)
                    combined = [
                        t for t in value.entries if t.chapter_id != cmd.chapter_id
                    ] + changed
                    value = value.model_copy(
                        update={
                            "entries": combined,
                            "related_tasks": related_tasks(combined, catalog),
                            "issues": [
                                s
                                for s in value.issues
                                if not s.startswith(str(cmd.chapter_id) + " ")
                            ],
                        }
                    )
            await self.persist(db, actor, value, receipt.request_ref)
            await complete_request(
                db,
                receipt,
                Ref(
                    owner="product",
                    type="material_edition",
                    id=str(value.edition_id),
                    revision=value.revision,
                ),
            )
            return EditionInfo.model_validate(
                value.model_dump(include=set(EditionInfo.model_fields))
            )


async def new_draft(
    db: AsyncConnection, template: Edition, identity: UUID, *, base: UUID | None = None
) -> Edition:
    number = await db.scalar(
        text(
            "SELECT coalesce(max(number),0)+1 FROM product.material_edition "
            "WHERE textbook_id=:book AND kind=:kind"
        ),
        {"book": template.textbook_id, "kind": template.kind},
    )
    return template.model_copy(
        update={
            "edition_id": identity,
            "base_edition_id": base,
            "number": number,
            "status": "draft",
            "created_at": datetime.now(UTC),
            "revision": 1,
            "pending": None,
        }
    )


def related_tasks(entries: list[MapTask], catalog: list[MapTask]) -> list[MapTask]:
    by_ref = {task.task_ref: task for task in catalog}
    included = {(t.task_ref.object_id, t.task_ref.version) for t in entries}
    queue = list(entries)
    result: list[MapTask] = []
    while queue:
        task = queue.pop()
        for dependency in task.prerequisites:
            item = by_ref.get(dependency.task_ref)
            key = (dependency.task_ref.object_id, dependency.task_ref.version)
            if item and key not in included:
                included.add(key)
                result.append(item)
                queue.append(item)
    return result


def select_tasks(
    selected: list[ChapterTask], catalog: list[MapTask], nodes: list[ContentNode]
) -> list[MapTask]:
    lookup = {t.task_ref: t for t in catalog}
    parents = {n.node_id: n.parent_id for n in nodes}
    chapters = {n.node_id for n in nodes if n.node_kind in {"chapter", "section", "unit"}}
    seen: set[tuple[UUID, UUID, int]] = set()
    result: list[MapTask] = []
    for entry in selected:
        task = lookup.get(entry.task_ref)
        key = (entry.chapter_id, entry.task_ref.object_id, entry.task_ref.version)
        if task is None or entry.chapter_id not in chapters or key in seen:
            raise RequestError(422, "invalid_reference", "任务或章节无效，或同一节内重复。")
        seen.add(key)
        if not entry.method_refs or not set(entry.method_refs) <= set(task.method_refs):
            raise RequestError(422, "invalid_reference", "所选方法不属于此任务。")
        for ref in entry.source_nodes:
            current = ref
            while current != entry.chapter_id:
                parent = parents.get(current)
                if parent is None:
                    raise RequestError(422, "invalid_reference", "例题来源不在选定章节。")
                current = parent
        indices = [task.method_refs.index(m) for m in entry.method_refs]
        used = list(dict.fromkeys(k for i in indices for k in task.method_knowledge[i]))
        result.append(
            task.model_copy(
                update={
                    "chapter_id": entry.chapter_id,
                    "source_nodes": entry.source_nodes,
                    "method_refs": entry.method_refs,
                    "method_names": [task.method_names[i] for i in indices],
                    "method_knowledge": [task.method_knowledge[i] for i in indices],
                    "knowledge": used,
                    "knowledge_names": [
                        task.knowledge_names[task.knowledge.index(k)] for k in used
                    ],
                }
            )
        )
    return result
