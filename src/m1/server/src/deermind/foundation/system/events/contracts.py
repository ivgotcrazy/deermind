"""事件保存的内部合同；只接受程序登记的类型，不接受任意表名或SQL。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from sqlalchemy.ext.asyncio import AsyncConnection

NonEmpty = Annotated[str, Field(min_length=1)]


class FactModel(BaseModel):
    """固定正文拒绝未知字段及隐式类型转换。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Ref(FactModel):
    owner: NonEmpty
    type: NonEmpty
    id: NonEmpty
    revision: Annotated[int, Field(ge=1)] | None = None
    version: Annotated[int, Field(ge=1)] | None = None
    path: str | None = None

    @model_validator(mode="after")
    def single_version(self) -> "Ref":
        if self.revision is not None and self.version is not None:
            raise ValueError("A reference cannot contain both revision and version")
        return self


class InlineContent(FactModel):
    storage: Literal["inline"]
    value: dict[str, JsonValue]


class FactRecord(FactModel):
    record_id: NonEmpty
    record_type: NonEmpty
    schema_version: Annotated[int, Field(ge=1)]
    content: InlineContent


class EventPayload(FactModel):
    records: list[FactRecord]


@dataclass(frozen=True)
class EventDraft:
    """身份由生产方预分配；本批仅接线服务端发生的内联事实。"""

    event_id: UUID
    event_type: str
    schema_version: int
    scope_kind: str
    scope_id: UUID
    owner_ref: Ref
    payload: dict[str, JsonValue]
    source_request_id: str | None
    causation_event_id: UUID | None = None
    subject_refs: tuple[Ref, ...] = ()
    source_execution_ref: UUID | None = None


@dataclass(frozen=True)
class ProducerAccess:
    """由受信入口构造的授权范围；不能从浏览器或AI输出直接反序列化。"""

    producer: str
    actor_ref: Ref
    scopes: frozenset[tuple[str, UUID]]
    source_event_ids: frozenset[UUID] = frozenset()


@dataclass(frozen=True)
class StoredEvent:
    draft: EventDraft
    commit_id: UUID
    correlation_id: UUID
    scope_event_seq: int
    recorded_at: datetime
    payload: EventPayload


@dataclass(frozen=True)
class EventRegistration:
    """所有者提供校验和确定性投影；底座不导入业务模块。"""

    event_type: str
    schema_version: int
    producer: str
    scope_kind: str
    payload_model: type[EventPayload]
    validate: Callable[[EventDraft, EventPayload], None]
    projector_id: str
    project: Callable[[AsyncConnection, StoredEvent], Awaitable[None]]


class EventConflict(ValueError):
    """范围序号或固定身份与现有事实冲突，调用方必须回滚事务。"""
