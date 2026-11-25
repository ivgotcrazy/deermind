"""业务命令的收据身份及已保存的结果引用。

分层定位：abstractions（跨层合同）
对外契约：CommandReceipt 与 ReceiptCommands 端口，供受理防重与结果补读使用。
边界约束：只定义收据身份与命令接口，不含幂等判定与存储实现。
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic import JsonValue

from deermind.abstractions.events import Ref


@dataclass(frozen=True)
class CommandReceipt:
    """一次业务命令的收据：请求引用与已保存结果引用（命令未完成时为空）。"""

    request_ref: UUID
    result_ref: Ref | None


class ReceiptCommands[Connection](Protocol):
    """命令收据端口：认领请求（幂等防重）、完成请求、补读已完成请求。"""

    async def claim_request(
        self,
        connection: Connection,
        *,
        principal_id: str,
        action: str,
        scope_id: str,
        request_id: str,
        normalized_input: dict[str, JsonValue],
        reserved_ref: UUID | None = None,
    ) -> CommandReceipt: ...

    async def complete_request(
        self,
        connection: Connection,
        receipt: CommandReceipt,
        result: Ref,
    ) -> CommandReceipt: ...

    async def find_completed_request(
        self,
        connection: Connection,
        principal: UUID,
        action: str,
        scope: UUID,
        request_id: str,
        normalized_input: dict[str, JsonValue] | None = None,
    ) -> CommandReceipt | None: ...
