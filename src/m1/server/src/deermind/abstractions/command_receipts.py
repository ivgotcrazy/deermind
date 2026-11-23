"""业务命令的收据身份及已保存的结果引用。"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic import JsonValue

from deermind.abstractions.events import Ref


@dataclass(frozen=True)
class CommandReceipt:
    request_ref: UUID
    result_ref: Ref | None


class ReceiptCommands[Connection](Protocol):
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
