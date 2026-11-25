"""读取已由业务调用者选定的领域对象固定版本。"""

from uuid import UUID

from pydantic import JsonValue, TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from deermind.abstractions.events import Ref

OBJECT_CONTENT = TypeAdapter(dict[str, JsonValue])


async def read_fixed_reference(
    db: AsyncConnection, domain: UUID, reference: Ref
) -> tuple[dict[str, JsonValue], UUID] | None:
    """构造者已经核准用途和身份；这里复核归域、对象种类及引用版本。"""
    if (
        reference.owner != "domain"
        or reference.type not in {"task", "solution", "task_instance"}
        or reference.version is None
        or reference.path is not None
    ):
        # 固定引用必须归属 domain、类型受限、带版本且不带片段路径。
        raise ValueError("Expected a fixed Domain reference")
    saved = (
        await db.execute(
            text(
                "SELECT v.content,v.source_event_id FROM domain.object_identity i "
                "JOIN domain.object_version v USING(object_id) "
                "WHERE i.object_id=:id AND i.domain_id=:domain AND i.kind=:kind "
                "AND v.version=:version AND NOT v.is_deleted"
            ),
            {
                "id": UUID(reference.id),
                "domain": domain,
                "kind": reference.type,
                "version": reference.version,
            },
        )
    ).one_or_none()
    if saved is None:
        # 归域/种类/版本不符或已删除，按无固定引用处理。
        return None
    return OBJECT_CONTENT.validate_python(saved.content, strict=True), saved.source_event_id
