"""工具描述与调用合同；权限和收据由底座执行。"""

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, JsonValue

from deermind.abstractions.ai.contracts import CallHandle
from deermind.abstractions.events import FactModel, Ref


class ToolResult(FactModel):
    status: Literal["ok", "not_found", "invalid_arguments", "source_changed"]
    data: dict[str, JsonValue]
    source_refs: list[Ref]
    owner_receipt_ref: Ref | None


@dataclass(frozen=True)
class ToolDescription:
    reference: Ref
    name: str
    description: str
    parameters: type[BaseModel]


class ToolService(Protocol):
    def descriptions(self) -> tuple[ToolDescription, ...]: ...
    async def invoke(
        self,
        handle: CallHandle,
        name: str,
        parameters: dict[str, JsonValue],
        turn: int,
        ordinal: int,
    ) -> ToolResult: ...
