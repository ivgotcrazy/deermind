"""按登记动作委托所有者查收据；不读取业务表，不派发工作。"""

from collections.abc import Awaitable, Callable, Mapping
from uuid import UUID

from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery
from pydantic import BaseModel

type ReceiptReader = Callable[[UUID, UUID, ReceiptQuery], Awaitable[BaseModel]]


class RequestReceipts:
    def __init__(self, readers: Mapping[tuple[str, str], ReceiptReader]) -> None:
        self.readers = dict(readers)

    async def read(self, principal: UUID, session: UUID, query: ReceiptQuery) -> BaseModel:
        reader = self.readers.get((query.action, query.resource_kind))
        if reader is None:
            raise RequestError(400, "invalid_request", "该动作或资源尚未开放收据查询。")
        return await reader(principal, session, query)
