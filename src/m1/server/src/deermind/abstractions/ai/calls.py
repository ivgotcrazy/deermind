"""AI调用服务接口；适配器不得穿透账本或附件实现。"""

from typing import Protocol
from uuid import UUID

from pydantic import JsonValue

from deermind.abstractions.ai.contracts import CallHandle, CallInput
from deermind.abstractions.ai.requests import ModelRequestFact
from deermind.abstractions.events import Ref


class AIRejected(ValueError):
    """只携带固定错误码，不向日志或Temporal错误复制模型材料和密钥。"""


class CallService(Protocol):
    async def prepare(self, incoming: CallInput) -> CallHandle: ...
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
