"""Build course and goal chapter views exclusively from their selected edition."""

from collections import defaultdict
from uuid import UUID, uuid5

from deermind.abstractions.events import Ref
from deermind.foundation.system.public.errors import RequestError
from deermind.product.materials.editions import read_edition
from deermind.product.public.chapter_associations import ChapterAssociationView
from deermind.product.public.courses import ChapterSnapshot
from deermind.product.public.material_editions import ContentNode, Edition, MapTask
from sqlalchemy.ext.asyncio import AsyncConnection


def association(identity: UUID, row: MapTask) -> ChapterAssociationView:
    key = uuid5(identity, f"{row.chapter_id}:{row.task_ref.object_id}:{row.task_ref.version}")
    return ChapterAssociationView(
        association_ref=Ref(owner="product", type="edition_chapter_task", id=str(key), revision=1),
        task_ref=row.task_ref,
        method_refs=row.method_refs,
        active=True,
    )


async def published(db: AsyncConnection, book: UUID, identity: UUID) -> Edition:
    value = await read_edition(db, book, identity)
    if value.kind != "extraction" or value.status != "published" or value.tree_id is None:
        raise RequestError(409, "invalid_reference", "请选择本教材已发布的教学提炼。")
    return value


async def chapters(db: AsyncConnection, book: UUID, identity: UUID) -> list[ChapterSnapshot]:
    value = await published(db, book, identity)
    assert value.tree_id is not None
    tree = await read_edition(db, book, value.tree_id)
    children: dict[UUID | None, list[ContentNode]] = defaultdict(list)
    for node in tree.nodes:
        children[node.parent_id].append(node)
    result: list[ChapterSnapshot] = []
    for node in tree.nodes:
        if node.node_kind not in {"unit", "chapter", "section"}:
            continue
        title = next(
            (
                str((c.content or {}).get("text", ""))
                for c in children[node.node_id]
                if c.node_kind == "heading"
            ),
            "未题名章节",
        )
        stack = list(reversed(children[node.node_id]))
        refs: list[Ref] = []
        while stack:
            item = stack.pop()
            if item.node_kind in {"unit", "chapter", "section"}:
                continue
            refs.append(
                Ref(
                    owner="product",
                    type="material_content_node",
                    id=str(item.node_id),
                    revision=tree.number,
                )
            )
            stack.extend(reversed(children[item.node_id]))
        result.append(
            ChapterSnapshot(
                chapter_id=node.node_id,
                revision=tree.number,
                title=title,
                page_refs=[
                    Ref(owner="product", type="material_page", id=str(p))
                    for p in node.covered_page_ids
                ],
                content_refs=refs,
                associations=[
                    association(identity, r) for r in value.entries if r.chapter_id == node.node_id
                ],
            )
        )
    return result
