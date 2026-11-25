"""工具描述与调用合同；权限和收据由底座执行。

分层定位：abstractions（AI 跨层合同）
对外契约：ToolResult、ToolDescription 与 ToolService 端口。
边界约束：只定义工具调用结果、描述与接口，授权、留痕、幂等由 foundation 执行。
"""

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, JsonValue

from deermind.abstractions.ai.contracts import CallHandle
from deermind.abstractions.events import FactModel, Ref


class ToolResult(FactModel):
    """工具调用结果：状态、数据、来源引用与所有者收据引用。"""

    status: Literal["ok", "not_found", "invalid_arguments", "source_changed"]
    data: dict[str, JsonValue]
    source_refs: list[Ref]
    owner_receipt_ref: Ref | None


@dataclass(frozen=True)
class ToolDescription:
    """下发给 SDK 的工具公开描述；校验与执行函数不随描述暴露。"""

    reference: Ref
    name: str
    description: str
    parameters: type[BaseModel]


class ToolService(Protocol):
    """工具服务端口：提供公开描述，并按调用身份受控执行工具。"""

    def descriptions(self) -> tuple[ToolDescription, ...]: ...
    async def invoke(
        self,
        handle: CallHandle,
        name: str,
        parameters: dict[str, JsonValue],
        turn: int,
        ordinal: int,
    ) -> ToolResult: ...
