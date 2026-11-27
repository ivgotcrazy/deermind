"""Validate a complete logical tree before projecting its nodes."""

from uuid import UUID

from deermind.product.public.material_editions import BookPage, ContentNode


def validate_tree(nodes: list[ContentNode], pages: list[BookPage]) -> None:
    by_id = {node.node_id: node for node in nodes}
    roots = [node for node in nodes if node.parent_id is None]
    if len(by_id) != len(nodes) or len(roots) != 1 or roots[0].node_kind != "book":
        raise ValueError("整本教材需要唯一的根和互不重复的节点。")
    allowed = {page.page_id for page in pages}
    order: set[tuple[UUID | None, int]] = set()
    children: dict[UUID, list[UUID]] = {}
    for node in nodes:
        covered = set(node.covered_page_ids)
        if len(covered) != len(node.covered_page_ids) or not covered <= allowed:
            raise ValueError("节点的原页引用重复或不属于该版教材。")
        key = (node.parent_id, node.sibling_order)
        if key in order:
            raise ValueError("同级内容的阅读顺序重复。")
        order.add(key)
        if node.parent_id is not None:
            parent = by_id.get(node.parent_id)
            if (
                parent is None
                or node.node_kind == "book"
                or not covered <= set(parent.covered_page_ids)
            ):
                raise ValueError("节点缺少有效父级，或父级未覆盖子节点的来源页。")
            children.setdefault(node.parent_id, []).append(node.node_id)
        if not covered:
            raise ValueError("每个节点都需要可定位的原页。")
    visited: set[UUID] = set()
    queue = [roots[0].node_id]
    while queue:
        current = queue.pop()
        visited.add(current)
        queue.extend(children.get(current, []))
    if len(visited) != len(nodes) or set(roots[0].covered_page_ids) != allowed:
        raise ValueError("内容树有不可达节点或缺少来源页。")
