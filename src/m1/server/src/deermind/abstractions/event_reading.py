"""事件读取的内部合同；身份和用途由受信入口提供，不从客户端反序列化。"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import JsonValue

from deermind.abstractions.events import FactModel, Ref

PAGE_DEFAULT = 50
PAGE_MAX = 100
RESPONSE_LIMIT = 4 * 1024 * 1024
FACT_READ_LIMIT = 32 * 1024 * 1024

Purpose = Literal[
    "student_history",
    "admin_review",
    "material_processing",
    "domain_intake",
    "task_supply",
    "learning_context",
    "evaluation_basis",
    "execution_support",
    "projection_rebuild",
]


class EventPartRef(FactModel):
    event_id: UUID
    record_id: str | None
    path: str


@dataclass(frozen=True)
class ReadAccess:
    """所有者已核验的本次授权；技术身份本身不赋予任意业务数据读取权。"""

    principal_id: str
    handler_id: str
    module: str
    purpose: Purpose
    authorization_ref: str
    scopes: frozenset[tuple[str, UUID]]
    source_event_ids: frozenset[UUID] | None = None
    resource_refs: tuple[Ref, ...] = ()
    execution_ref: UUID | None = None
    maintenance_ref: str | None = None


@dataclass(frozen=True)
class ReadHandler:
    handler_id: str
    module: str
    purpose: Purpose


class EventFact(FactModel):
    """从唯一事实表读取的完整信封；不会作为浏览器响应直接返回。"""

    event_id: UUID
    commit_id: UUID
    event_type: str
    schema_version: int
    producer: str
    scope_kind: str
    scope_id: UUID
    owner_ref: Ref
    subject_refs: list[Ref]
    actor_ref: Ref | None
    source_execution_ref: UUID | None
    source_request_id: str | None
    causation_event_id: UUID | None
    correlation_id: UUID
    scope_event_seq: int
    occurred_at: datetime | None
    recorded_at: datetime
    time_basis: Literal["server_recorded", "referenced_fact", "unknown"]
    time_source_ref: dict[str, JsonValue] | None
    client_reported_at: datetime | None
    payload: dict[str, JsonValue]


@dataclass(frozen=True)
class ReadGrant:
    """所有者授予本事件的字段；None表示该固定Schema全部字段，缺项表示拒绝。"""

    record_fields: Mapping[tuple[str, int], frozenset[str] | None]
    payload_fields: frozenset[str]
    summary: str
    subject_refs: tuple[Ref, ...] = ()


@dataclass(frozen=True)
class ReadPolicy:
    event_type: str
    schema_version: int
    module: str
    purpose: Purpose
    # 参数为授权及完整事件信封；回调只判断本模块规则，不调用模型或写入数据。
    authorize: Callable[[ReadAccess, EventFact], ReadGrant | None]


@dataclass(frozen=True)
class EventFilter:
    event_types: tuple[str, ...] = ()
    subject_ref: Ref | None = None
    correlation_id: UUID | None = None
    causation_event_id: UUID | None = None
    recorded_from: datetime | None = None
    recorded_to: datetime | None = None


def pointer_parts(path: str) -> list[str]:
    """仅接受RFC6901指针；不把路径当成URL、SQL或可执行表达式。"""
    if path == "":
        return []
    if not path.startswith("/"):
        raise ValueError("Expected a JSON Pointer")
    parts: list[str] = []
    for token in path[1:].split("/"):
        index = 0
        while index < len(token):
            if token[index] == "~":
                if index + 1 >= len(token) or token[index + 1] not in "01":
                    raise ValueError("Invalid JSON Pointer escape")
                index += 1
            index += 1
        parts.append(token.replace("~1", "/").replace("~0", "~"))
    return parts


def fragment(value: JsonValue, parts: list[str]) -> JsonValue:
    """缺少已获准字段与非法数组下标分别报告；不猜测正文。"""
    for part in parts:
        if isinstance(value, dict):
            value = value[part]
        elif isinstance(value, list):
            if not part.isascii() or not part.isdecimal() or str(int(part)) != part:
                raise ValueError("Invalid JSON Pointer array index")
            value = value[int(part)]
        else:
            raise ValueError("JSON Pointer does not address a container")
    return value
