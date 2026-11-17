"""事件保存的内部合同；只接受程序登记的类型，不接受任意表名或SQL。"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

NonEmpty = Annotated[str, Field(min_length=1)]
INLINE_LIMIT = 32 * 1024
EVENT_LIMIT = 1024 * 1024


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


class FileContent(FactModel):
    """固定文件身份与完整性信息；不是路径或读取授权。"""

    storage: Literal["file"]
    file_id: UUID
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    media_type: Literal["application/json"]


class FactRecord(FactModel):
    record_id: NonEmpty
    record_type: NonEmpty
    schema_version: Annotated[int, Field(ge=1)]
    content: InlineContent | FileContent


class EventPayload(FactModel):
    records: list[FactRecord]


@dataclass(frozen=True)
class EventDraft:
    """身份由生产方预分配；本批接线服务端发生的事实。"""

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
class PreparedEvents:
    """事务外已核验的附件；完整正文是固定JSON字符串，提交时重新校验。"""

    drafts: tuple[EventDraft, ...]
    decoded_payloads: tuple[str, ...]
    access: ProducerAccess


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
    """所有者提供事件正文校验；事件类型不绑定投影器。"""

    event_type: str
    schema_version: int
    producer: str
    scope_kind: str
    payload_model: type[EventPayload]
    validate: Callable[[EventDraft, EventPayload], None]
    record_models: Mapping[tuple[str, int], type[FactModel]] = field(
        default_factory=lambda: dict[tuple[str, int], type[FactModel]]()
    )


class EventConflict(ValueError):
    """范围序号或固定身份与现有事实冲突，调用方必须回滚事务。"""
