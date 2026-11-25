"""AI 调用服务接口；适配器不得穿透账本或附件实现。

分层定位：abstractions（AI 跨层合同）
对外契约：AIRejected 固定错误码与 CallService 端口。
边界约束：只定义调用生命周期接口，账本、附件、预算实现由 foundation 承接。
"""

from typing import Protocol
from uuid import UUID

from pydantic import JsonValue

from deermind.abstractions.ai.contracts import CallHandle, CallInput, PromptCallInput
from deermind.abstractions.ai.requests import ModelRequestFact
from deermind.abstractions.events import Ref


class AIRejected(ValueError):
    """只携带固定错误码，不向日志或Temporal错误复制模型材料和密钥。"""


class CallService(Protocol):
    """AI 调用账本端口：准备调用、剩余时限、预约/结算模型请求、候选落盘、失败与材料读写。"""
    async def prepare(self, incoming: CallInput | PromptCallInput) -> CallHandle: ...
    async def remaining(self, handle: CallHandle) -> float: ...
    async def reserve(
        self,
        handle: CallHandle,
        ordinal: int,
        transport: int,
        request_ref: Ref,
        input_tokens: int,
        *,
        repair: bool,
    ) -> ModelRequestFact: ...
    async def settle(
        self,
        handle: CallHandle,
        request: ModelRequestFact,
        *,
        response_ref: Ref | None,
        actual_usage: tuple[int, int] | None,
        provider_id: str | None,
        error_code: str | None,
    ) -> None: ...
    async def candidate(self, handle: CallHandle, content: dict[str, JsonValue]) -> UUID: ...
    async def fail(self, handle: CallHandle, error_code: str) -> None: ...
    async def save_material(
        self,
        content: dict[str, JsonValue],
        *,
        actor: Ref,
        source: Ref,
        artifact_key: str,
        max_bytes: int,
    ) -> Ref: ...
    async def read_material(
        self, reference: Ref, *, source: Ref, max_bytes: int
    ) -> dict[str, JsonValue]: ...
