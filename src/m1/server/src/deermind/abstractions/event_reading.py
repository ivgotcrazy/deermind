"""事件读取的内部合同；范围与取材条件由业务入口核定。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import JsonValue

from deermind.abstractions.events import FactModel, Ref, StoredEvent

PAGE_DEFAULT = 50
PAGE_MAX = 100
RESPONSE_LIMIT = 4 * 1024 * 1024
FACT_READ_LIMIT = 32 * 1024 * 1024


class EventPartRef(FactModel):
    event_id: UUID
    record_id: str | None
    path: str


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
class ScanPage:
    events: tuple[StoredEvent, ...]
    scanned_through_seq: int
    upper_seq: int


@dataclass(frozen=True)
class EventFilter:
    event_types: tuple[str, ...] = ()
    subject_ref: Ref | None = None
    correlation_id: UUID | None = None
    causation_event_id: UUID | None = None
    recorded_from: datetime | None = None
    recorded_to: datetime | None = None
    event_id: UUID | None = None


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
