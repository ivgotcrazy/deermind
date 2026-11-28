"""Model outputs use local node keys; the program owns page references and stable identities."""

import json
from uuid import UUID, uuid5

from deermind.abstractions.events import FactModel
from deermind.product.materials.content_tree import validate_tree
from deermind.product.public.material_editions import (
    BookPage,
    ContentNode,
    NodeKind,
    TeachingModel,
)
from pydantic import Field, JsonValue


class OutlineItem(FactModel):
    key: str
    parent: str
    kind: NodeKind
    text: str
    structured_json: str | None = None
    pages: list[int]
    order: int = Field(ge=1)


class OutlineBatch(FactModel):
    nodes: list[OutlineItem]
    remove: list[str] = Field(default_factory=list)
    printed_pages: dict[str, str] = Field(default_factory=dict)


class TeachingModelBatch(TeachingModel):
    gaps: list[str]


def assemble(
    identity: UUID,
    pages: list[BookPage],
    batches: list[OutlineBatch],
    original: list[ContentNode] | None = None,
) -> tuple[list[ContentNode], list[BookPage]]:
    existing = {str(n.node_id): n for n in original or []}
    root = next(
        (n.node_id for n in existing.values() if n.parent_id is None), uuid5(identity, "book")
    )

    def identify(key: str) -> UUID:
        if key == "book":
            return root
        return existing[key].node_id if key in existing else uuid5(identity, key)

    nodes = {n.node_id: n for n in existing.values()}
    nodes[root] = ContentNode(
        node_id=root,
        parent_id=None,
        node_kind="book",
        sibling_order=1,
        content=None,
        covered_page_ids=[p.page_id for p in pages],
    )
    labels: dict[str, str] = {}
    valid_pages = {p.page_id for p in pages}
    for batch in batches:
        labels.update(batch.printed_pages)
        for key in batch.remove:
            if key not in existing or identify(key) == root:
                raise ValueError("修正引用了不存在或不可移除的节点。")
            nodes.pop(identify(key), None)
        for item in batch.nodes:
            if item.kind == "book" and item.key == "book" and not item.parent:
                continue  # The application already owns the root and its page coverage.
            if item.kind == "book" or not item.parent or not item.key or item.key == "book":
                raise ValueError("原文节点的类型或父节点无效。")
            content: dict[str, JsonValue] = {"text": item.text} if item.text else {}
            if item.structured_json:
                structured = json.loads(item.structured_json)
                if not isinstance(structured, dict):
                    raise ValueError("图表或公式正文必须是对象。")
                content["structure"] = structured
            identifier = identify(item.key)
            if any(p < 1 or p > len(pages) for p in item.pages):
                raise ValueError("原页序号不属于本版教材。")
            node = ContentNode(
                node_id=identifier,
                parent_id=identify(item.parent),
                node_kind=item.kind,
                sibling_order=item.order,
                content=content or None,
                covered_page_ids=[pages[p - 1].page_id for p in item.pages],
            )
            if not set(node.covered_page_ids) <= valid_pages:
                raise ValueError("原页引用超出教材范围。")
            nodes[identifier] = node
    # Propagate physical page coverage upward; detect cycles before traversal.
    coverage = {key: set(node.covered_page_ids) for key, node in nodes.items()}
    for key, node in nodes.items():
        parent = node.parent_id
        seen = {key}
        while parent is not None:
            if parent in seen or parent not in nodes:
                raise ValueError("内容树有环或缺少父节点。")
            coverage[parent].update(node.covered_page_ids)
            seen.add(parent)
            parent = nodes[parent].parent_id
    ranked = {p.page_id: i for i, p in enumerate(pages)}
    rows = [
        node.model_copy(update={"covered_page_ids": sorted(coverage[key], key=ranked.__getitem__)})
        for key, node in nodes.items()
    ]
    if len(rows) <= 1 or not valid_pages <= {
        p for n in rows if n.parent_id for p in n.covered_page_ids
    }:
        raise ValueError("模型未完整处理给定教材页。")
    validate_tree(rows, pages)
    return rows, [
        p.model_copy(update={"printed": labels.get(str(i), p.printed)})
        for i, p in enumerate(pages, 1)
    ]
