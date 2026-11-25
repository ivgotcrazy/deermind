"""事件读取的内部合同；范围与取材条件由业务入口核定。

分层定位：abstractions（跨层合同）
对外契约：EventFact、EventFilter、ScanPage 及 JSON Pointer 解析辅助供读取端口使用。
边界约束：只定义读取数据结构与指针解析，不含授权核验与查询实现。
"""

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
    """定位某事件内一条记录或一个字段的引用；path 为 JSON Pointer。"""

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
    """一次扫描返回的事件页，附带已扫过的序号与本次上界序号，供分页接续。"""

    events: tuple[StoredEvent, ...]
    scanned_through_seq: int
    upper_seq: int


@dataclass(frozen=True)
class EventFilter:
    """事件读取条件集合；各条件全部可选，空集合表示不限制。"""

    event_types: tuple[str, ...] = ()
    subject_ref: Ref | None = None
    correlation_id: UUID | None = None
    causation_event_id: UUID | None = None
    recorded_from: datetime | None = None
    recorded_to: datetime | None = None
    event_id: UUID | None = None


def pointer_parts(path: str) -> list[str]:
    """仅接受RFC6901指针；不把路径当成URL、SQL或可执行表达式。"""
    # 空指针定位整个文档，返回空段列表。
    if path == "":
        return []
    # 非斜杠起始不符合 RFC6901 指针格式。
    if not path.startswith("/"):
        raise ValueError("Expected a JSON Pointer")
    parts: list[str] = []
    # 按斜杠拆出各段令牌，逐段还原转义。
    for token in path[1:].split("/"):
        index = 0
        # 扫描令牌内转义符，校验 ~0/~1 写法合法。
        while index < len(token):
            if token[index] == "~":
                # 转义符后必须跟 0 或 1，否则判非法转义。
                if index + 1 >= len(token) or token[index + 1] not in "01":
                    raise ValueError("Invalid JSON Pointer escape")
                index += 1
            index += 1
        parts.append(token.replace("~1", "/").replace("~0", "~"))
    return parts


def fragment(value: JsonValue, parts: list[str]) -> JsonValue:
    """缺少已获准字段与非法数组下标分别报告；不猜测正文。"""
    # 逐段下钻到目标字段；每段按当前值类型选择取值方式。
    for part in parts:
        if isinstance(value, dict):
            value = value[part]
        elif isinstance(value, list):
            # 数组下标须为十进制非负整数且无前导零等非法写法。
            if not part.isascii() or not part.isdecimal() or str(int(part)) != part:
                raise ValueError("Invalid JSON Pointer array index")
            value = value[int(part)]
        else:
            # 当前值既非对象也非数组，指针无法继续寻址。
            raise ValueError("JSON Pointer does not address a container")
    return value
