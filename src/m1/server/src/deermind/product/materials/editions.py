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
from deermind.product.materials.teaching_copy import copy_legacy
from deermind.product.materials.teaching_model import build_teaching, validate_model
from deermind.product.persistence.receipts import claim_request, complete_request
from deermind.product.public.authentication import SessionView
from deermind.product.public.material_editions import (
    BookPage,
    Edition,
    EditionCommand,
    EditionInfo,
    EditionUsage,
    MapTask,
    StudentBook,
    TeachingModel,
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
    result = Edition.model_validate_json(
        to_json(
            {
                **{key: row[key] for key in _COLUMNS.split(",")},
                "teaching": row["teaching"],
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

    if result.status == "draft" and isinstance(result.teaching, list):
        return result.model_copy(update={"teaching": copy_legacy(result.teaching)})
    return result


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

    async def catalog(self, book: UUID, edition: UUID | None) -> list[MapTask]:
        """Read this book's published catalogue. Explicit versions never fall back to latest."""
        async with self.engine.connect() as db:
            if edition is None:
                edition = await db.scalar(
                    text(
                        "SELECT edition_id FROM product.material_edition WHERE textbook_id=:book "
                        "AND kind='extraction' AND status='published' ORDER BY number DESC LIMIT 1"
                    ),
                    {"book": book},
                )
                if edition is None:
                    return []
            value = await read_edition(db, book, edition)
            if value.kind != "extraction" or value.status != "published":
                raise RequestError(404, "not_found", "未找到本教材的已发布教学提炼。")
            return value.entries

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
                if value.kind == "extraction" and value.teaching is None:
                    raise RequestError(
                        422, "invalid_teaching", "该快照只保存了索引，请从内容树生成草稿。"
                    )
                value = await new_draft(db, value, uuid4(), base=value.edition_id)
            elif cmd.action == "discard":
                if value.kind == "tree":
                    used = await db.scalar(
                        text(
                            "SELECT '教学提炼 v' || number FROM product.material_edition "
                            "WHERE tree_id=:id AND status<>'discarded' ORDER BY number LIMIT 1"
                        ),
                        {"id": identity},
                    )
                else:
                    used = await db.scalar(
                        text(
                            "SELECT '评估标准《' || name || '》' FROM evaluation.assessment_model "
                            "WHERE extraction_id=:id UNION ALL SELECT '目标《' || title || '》' "
                            "FROM product.learning_target_version WHERE extraction_id=:id LIMIT 1"
                        ),
                        {"id": identity},
                    )
                if used:
                    raise RequestError(409, "edition_in_use", f"{used} 正在使用此版本，无法删除。")
                value = value.model_copy(
                    update={"status": "discarded", "revision": value.revision + 1}
                )
            elif value.status != "draft" or cmd.action == "copy":
                raise RequestError(409, "revision_conflict", "已发布版本只读，请从发布版建草稿。")
            else:
                value = value.model_copy(update={"revision": value.revision + 1})
                if cmd.action == "publish":
                    if (
                        value.pending is not None
                        or value.issues
                        or (value.kind == "extraction" and not (value.teaching or value.entries))
                    ):
                        raise RequestError(409, "incomplete", "请先处理待核对内容并补全教学任务。")
                    if value.kind == "tree":
                        validate_tree(value.nodes, value.pages)
                    elif isinstance(value.teaching, TeachingModel) and value.tree_id is not None:
                        tree = await read_edition(db, book, value.tree_id)
                        entries, members, paths = build_teaching(
                            value.edition_id, value.teaching, tree.nodes
                        )
                        await self.materials.domain.publish_members(
                            db,
                            imported.domain_id,
                            actor,
                            receipt.request_ref,
                            value.edition_id,
                            members,
                            paths,
                        )
                        value = value.model_copy(update={"entries": entries, "related_tasks": []})
                    else:
                        raise RequestError(
                            422, "invalid_teaching", "缺少教学定义，请选择已发布内容树重新提炼。"
                        )
                    value = value.model_copy(update={"status": "published"})
                elif cmd.action == "edit_tree":
                    if value.kind != "tree" or cmd.nodes is None:
                        raise RequestError(400, "invalid_reference", "请选择内容树草稿。")
                    try:
                        validate_tree(cmd.nodes, value.pages)
                    except ValueError as exc:
                        raise RequestError(422, "invalid_tree", str(exc)) from exc
                    value = value.model_copy(update={"nodes": cmd.nodes, "pending": None})
                elif cmd.action == "edit_teaching":
                    if value.kind != "extraction" or cmd.teaching is None:
                        raise RequestError(422, "invalid_reference", "请选择教学提炼草稿。")
                    assert value.tree_id is not None
                    tree = await read_edition(db, book, value.tree_id)
                    validate_model(cmd.teaching, tree.nodes)
                    value = value.model_copy(
                        update={"teaching": cmd.teaching, "entries": [], "issues": []}
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
            "teaching": copy_legacy(template.teaching)
            if isinstance(template.teaching, list)
            else template.teaching,
            "base_edition_id": base,
            "entries": [] if template.teaching is not None else template.entries,
            "related_tasks": [] if template.teaching is not None else template.related_tasks,
            "number": number,
            "status": "draft",
            "created_at": datetime.now(UTC),
            "revision": 1,
            "pending": None,
        }
    )
