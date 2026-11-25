"""等待与发布结果的数据合同。

分层定位：abstractions（跨层合同）
对外契约：ResultKey、Publication、ResultView、Condition、Wait、Handling 及等待服务端口 Protocol。
边界约束：只定义等待条件、结果视图与接口，不含等待匹配与恢复实现。
"""

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, JsonValue

from deermind.abstractions.events import FactModel, NonEmpty, Ref
from deermind.abstractions.executions import RunInput


class ResultKey(FactModel):
    """结果定位键：空间、触发事件、生产方与结果种类，全局唯一确定一份结果。"""

    scope_id: UUID
    trigger_event_id: UUID
    producer: NonEmpty
    result_kind: NonEmpty


class Publication(ResultKey):
    """已发布的结果：产出执行、结果引用、相关引用、正文与发布时间。"""

    execution_id: UUID
    attempt_id: UUID
    result_ref: Ref
    publication_refs: list[Ref]
    payload: dict[str, JsonValue]
    event_id: UUID
    published_at: datetime


class ResultView(FactModel):
    """按授权读取到的结果状态视图：可用、等待、失败或未找到。"""

    state: Literal["available", "pending", "failed", "not_found"]
    publication: Publication | None = None
    failure_ref: Ref | None = None


class Condition(FactModel):
    """仅固定类型、范围和等值；更复杂业务条件在登记的只读probe中核对。"""

    event_types: list[NonEmpty] = Field(min_length=1)
    scope_kind: NonEmpty
    scope_id: UUID
    equals: dict[str, str] = Field(default_factory=dict)
    result_key: ResultKey | None = None


class Wait(FactModel):
    """一条等待登记：命中条件、探测引用、时限、恢复动作与最终处置结果。"""

    wait_id: UUID
    owner_ref: Ref
    execution_id: UUID
    step_key: NonEmpty
    condition: Condition
    condition_hash: NonEmpty
    probe_ref: Ref
    deadline_at: datetime
    resume_action_id: UUID
    on_match: NonEmpty
    on_timeout: NonEmpty
    resolution: Literal["pending", "matched", "timed_out", "cancelled"]
    matched_event_ref: UUID | None
    result_ref: Ref | None
    created_at: datetime
    resolved_at: datetime | None


class Handling(FactModel):
    """等待命中后的处理承诺状态：待处理、已提交、失败或取消，附回执与失败引用。"""

    wait_id: UUID
    resume_action_id: UUID
    state: Literal["awaiting", "committed", "failed", "cancelled"]
    handling_receipt_ref: Ref | None
    failure_ref: Ref | None
    updated_at: datetime


class Match(FactModel):
    """命中的事件及其可选结果引用。"""

    event_id: UUID
    result_ref: Ref | None


class WaitCall(FactModel):
    """等待服务调用输入：执行身份与等待编号。"""

    run: RunInput
    wait_id: UUID


class WaitService(Protocol):
    """等待服务端口：探测条件是否满足、处理命中并提交恢复动作。"""

    async def probe(self, call: WaitCall) -> Wait: ...
    async def handle(self, call: WaitCall) -> Handling: ...
